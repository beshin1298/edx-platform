"""
Utils for discussion API.
"""

from django.contrib.auth.models import User  # lint-amnesty, pylint: disable=imported-auth-user
from django.core.paginator import Paginator
from django.db.models.functions import Length

from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole
from lms.djangoapps.discussion.django_comment_client.utils import has_discussion_privileges
from openedx.core.djangoapps.django_comment_common.models import (
    Role,
    FORUM_ROLE_ADMINISTRATOR,
    FORUM_ROLE_MODERATOR,
    FORUM_ROLE_GROUP_MODERATOR,
    FORUM_ROLE_COMMUNITY_TA,
)


def discussion_open_for_user(course, user):
    """
    Check if course discussion are open or not for user.

    Arguments:
            course: Course to check discussions for
            user: User to check for privileges in course
    """
    return course.forum_posts_allowed or has_discussion_privileges(user, course.id)


def set_attribute(threads, attribute, value):
    """
    Iterates over the list of dicts and assigns the provided value to the given attribute

    Arguments:
        threads: List of threads (dict objects)
        attribute: the key for thread dict
        value: the value to assign to the thread attribute
    """
    for thread in threads:
        thread[attribute] = value
    return threads


def get_usernames_from_search_string(course_id, search_string, page_number, page_size):
    """
    Gets usernames for all users in course that match string.

    Args:
            course_id (CourseKey): Course to check discussions for
            search_string (str): String to search matching
            page_number (int): Page number to fetch
            page_size (int): Number of items in each page

    Returns:
            page_matched_users (str): comma seperated usernames for the page
            matched_users_count (int): count of matched users in course
            matched_users_pages (int): pages of matched users in course
    """
    matched_users_in_course = User.objects.filter(
        courseenrollment__course_id=course_id,
        username__icontains=search_string).order_by(Length('username').asc()).values_list('username', flat=True)
    if not matched_users_in_course:
        return '', 0, 0
    matched_users_count = len(matched_users_in_course)
    paginator = Paginator(matched_users_in_course, page_size)
    page_matched_users = paginator.page(page_number)
    matched_users_pages = int(matched_users_count / page_size)
    return ','.join(page_matched_users), matched_users_count, matched_users_pages


def get_usernames_for_course(course_id, page_number, page_size):
    """
    Gets usernames for all users in course.

    Args:
            course_id (CourseKey): Course to check discussions for
            page_number (int): Page numbers to fetch
            page_size (int): Number of items in each page

    Returns:
            page_matched_users (str): comma seperated usernames for the page
            matched_users_count (int): count of matched users in course
            matched_users_pages (int): pages of matched users in course
    """
    matched_users_in_course = User.objects.filter(courseenrollment__course_id=course_id,)\
        .order_by(Length('username').asc()).values_list('username', flat=True)
    if not matched_users_in_course:
        return '', 0, 0
    matched_users_count = len(matched_users_in_course)
    paginator = Paginator(matched_users_in_course, page_size)
    page_matched_users = paginator.page(page_number)
    matched_users_pages = int(matched_users_count / page_size)
    return ','.join(page_matched_users), matched_users_count, matched_users_pages


def add_stats_for_users_with_no_discussion_content(course_stats, users_in_course):
    """
    Update users stats for users with no discussion stats available in course
    """
    users_returned_from_api = [user['username'] for user in course_stats]
    user_list = users_in_course.split(',')
    users_with_no_discussion_content = set(user_list) ^ set(users_returned_from_api)
    updated_course_stats = course_stats
    for user in users_with_no_discussion_content:
        updated_course_stats.append({
            'username': user,
            'threads': 0,
            'replies': 0,
            'responses': 0,
            'active_flags': 0,
            'inactive_flags': 0,
        })
    updated_course_stats = sorted(updated_course_stats, key=lambda d: len(d['username']))
    return updated_course_stats


def get_course_staff_users_list(course_id):
    """
    Gets user ids for Staff roles for course discussions.
    Roles Course Instructor and Course Staff.
    """
    # TODO: cache course_staff_user_ids if we need to improve perf
    course_staff_user_ids = []
    staff = list(CourseStaffRole(course_id).users_with_role().values_list('id', flat=True))
    admins = list(CourseInstructorRole(course_id).users_with_role().values_list('id', flat=True))
    course_staff_user_ids.extend(staff)
    course_staff_user_ids.extend(admins)
    return list(set(course_staff_user_ids))


def get_course_ta_users_list(course_id):
    """
    Gets user ids for TA roles for course discussions.
    Roles include Community TA and Group Community TA.
    """
    # TODO: cache ta_users_ids if we need to improve perf
    ta_users_ids = [
        user.id
        for role in Role.objects.filter(name__in=[FORUM_ROLE_GROUP_MODERATOR,
                                                  FORUM_ROLE_COMMUNITY_TA], course_id=course_id)
        for user in role.users.all()
    ]
    return ta_users_ids


def get_moderator_users_list(course_id):
    """
    Gets user ids for Moderator roles for course discussions.
    Roles include Discussion Administrator and Discussion Moderator.
    """
    # TODO: cache moderator_user_ids if we need to improve perf
    moderator_user_ids = [
        user.id
        for role in Role.objects.filter(
            name__in=[FORUM_ROLE_ADMINISTRATOR, FORUM_ROLE_MODERATOR],
            course_id=course_id
        )
        for user in role.users.all()
    ]
    return moderator_user_ids


def filter_topic_from_discussion_id(discussion_id, topics_list):
    """
    Returns topic based on discussion id
    """
    for topic in topics_list:
        if topic.get("id") == discussion_id:
            return topic
    return {}


def create_discussion_children_from_ids(children_ids, blocks, topics):
    """
    Takes ids of discussion and return discussion dictionary
    """
    discussions = []
    for child_id in children_ids:
        topic = blocks.get(child_id)
        if topic.get('type') == 'vertical':
            discussions_id = topic.get('discussions_id')
            topic = filter_topic_from_discussion_id(discussions_id, topics)
        if topic:
            discussions.append(topic)
    return discussions


def create_blocks_params(course_usage_key, user):
    """
    Returns param dict that is needed to get blocks
    """
    return {
        'usage_key': course_usage_key,
        'user': user,
        'depth': None,
        'nav_depth': None,
        'requested_fields': {
            'display_name',
            'student_view_data',
            'children',
            'discussions_id',
            'type',
            'block_types_filter'
        },
        'block_counts': set(),
        'student_view_data': {'discussion'},
        'return_type': 'dict',
        'block_types_filter': {
            'discussion',
            'chapter',
            'vertical',
            'sequential',
            'course'
        }
    }


def create_topics_v3_structure(blocks, topics):
    """
    Create V3 topics structure from blocks and v2 topics
    """
    non_courseware_topics = [
        dict({**topic, 'courseware': False})
        for topic in topics
        if topic.get('usage_key', '') is None
    ]
    courseware_topics = []
    for key, value in blocks.items():
        if value.get("type") == "chapter":
            value['courseware'] = True
            courseware_topics.append(value)
            value['children'] = create_discussion_children_from_ids(
                value['children'],
                blocks,
                topics,
            )
            subsections = value.get('children')
            for subsection in subsections:
                subsection['children'] = create_discussion_children_from_ids(
                    subsection['children'],
                    blocks,
                    topics,
                )
    return non_courseware_topics + courseware_topics
