"""
Signal handlers related to discussions.
"""
import logging

from django.dispatch import receiver
from opaque_keys.edx.keys import CourseKey

from django_comment_common import signals
from lms.djangoapps.discussion import tasks
from openedx.core.djangoapps.site_configuration.models import SiteConfiguration
from openedx.core.djangoapps.theming.helpers import get_current_site


log = logging.getLogger(__name__)


ENABLE_FORUM_NOTIFICATIONS_FOR_SITE_KEY = 'enable_forum_notifications'


@receiver(signals.comment_created)
def send_discussion_email_notification(sender, user, post, **kwargs):
    current_site = get_current_site()
    if current_site is None:
        log.info('Discussion: No current site, not sending notification about post: %s.', post.id)
        return

    try:
        if not current_site.configuration.get_value(ENABLE_FORUM_NOTIFICATIONS_FOR_SITE_KEY, False):
            log_message = 'Discussion: notifications not enabled for site: %s. Not sending message about post: %s.'
            log.info(log_message, current_site, post.id)
            return
    except SiteConfiguration.DoesNotExist:
        log_message = 'Discussion: No SiteConfiguration for site %s. Not sending message about post: %s.'
        log.info(log_message, current_site, post.id)
        return

    send_message(post, current_site)


def send_message(comment, site):
    thread = comment.thread
    context = {
        'course_id': unicode(thread.course_id),
        'comment_body': comment.body,
        'thread_id': thread.id,
        'thread_title': thread.title,
        'thread_author_name': thread.username,
        'thread_author_id': thread.user_id,
        'thread_created_at': thread.created_at,  # comment_client models dates are already serialized
        'thread_commentable_id': thread.commentable_id,

        # values unique to comments (replies). This can change as needed.
        'comment_id': comment.id,
        'comment_author_name': comment.username,
        'comment_author_id': comment.user_id,
        'comment_created_at': comment.created_at,  # comment_client models dates are already serialized
        'site_id': site.id
    }
    tasks.send_ace_message.apply_async(args=[context])

def get_course_urls(course_id):
    if "Demo" in course_id or "demo" in course_id:
        return (
            "http://x1v16stepdo18:8000/courses/course-v1:edX+DemoX+Demo_Course/course/",
            "http://x1v16stepdo18:8000/courses/course-v1:edX+DemoX+Demo_Course/search/?query=",
            "http://x1v16stepdo18:8000/courses/course-v1%3AedX%2BDemoX%2BDemo_Course/discussion/forum/?ajax=1&page=1&sort_key=activity&sort_order=desc",
            "",
            ""
        )
    else:
        return (
            "http://x1v16stepdo18:8000/courses/course-v1:Microsoft+Dat206+May30_2/course/",
            "http://x1v16stepdo18:8000/courses/course-v1:Microsoft+Dat206+May30_2/search/?query=",
            "http://x1v16stepdo18:8000/courses/course-v1%3AMicrosoft%2BDat206%2BMay30_2/discussion/forum/?ajax=1&page=1&sort_key=activity&sort_order=desc",
            "http://x1v16stepdo18:8000/courses/course-v1:Microsoft+Dat206+May30_2/42e780a3df3d4aaf8dda4198192254e2/",
            "http://x1v16stepdo18:8000/courses/course-v1:Microsoft+Dat206+May30_2/ce42d37f282141469a3c0bd38b6766d7/"
        )

@receiver(signals.thread_created)
def send_discussion_notification(sender, user, post, **kwargs):
    thread = post
    home, search_content, forum_threads, syllabus, faq = get_course_urls(thread.course_id)
    context = {
        'course_id': unicode(thread.course_id),
        'comment_body': thread.body,
        'thread_id': thread.id,
        'thread_title': thread.title,
        'thread_author_name': thread.username,
        'thread_author_id': thread.user_id,
        'thread_created_at': thread.created_at,  # comment_client models dates are already serialized
        'thread_commentable_id': thread.commentable_id,

        # values unique to threads (new posts). This can change as needed.
        'thread_type': thread.thread_type,
        'home_url': home,
        'search_content_url': search_content,
        'forum_threads_url': forum_threads,
        'syllabus_url': syllabus,
        'faq_url': faq
    }
    #todo: use response
    response = tasks.post_ace_message.apply_async(args=[context])
    if response.result.status_code == 200 and response.result.content:
        reply = {'body': 'this is a reply ' + response.result.content}

        course_key = CourseKey.from_string(thread.course_id)
        thread_id = thread.id
        tasks.write_reply.apply_async(args=[reply, course_key, thread_id])
