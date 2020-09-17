"""
An XBlock that allows learners to chat with a bot, where the bot follows
a script and the learner can choose among possible responses.

Authors define the script as a set of "steps", where each step has an
ID, a message (or several), and a set of up to three responses, where
each response includes the ID of the next step to respond with.
"""

import json
import os
from builtins import str

import pkg_resources
import webob
import yaml
from django import utils
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.http import Http404
from past.builtins import basestring
from web_fragments.fragment import Fragment
from xblock.core import XBlock
from xblock.fields import Boolean, List, Scope, String
from xblock.validation import ValidationMessage
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable import StudioEditableXBlockMixin

from .default_data import (
    BOT_MESSAGE_ANIMATION_DELAY,
    BUTTONS_ENTERING_TRANSITION_DURATION,
    BUTTONS_LEAVING_TRANSITION_DURATION,
    DEFAULT_BOT_ID,
    DEFAULT_DATA,
    MAX_USER_RESPONSES,
    NAME_PLACEHOLDER,
    SCROLL_DELAY,
    TYPING_DELAY_PER_CHARACTER,
    USER_ID,
    USER_MESSAGE_ANIMATION_DELAY,
)
from .utils import _

try:
    from openedx.core.djangoapps.user_api.accounts.image_helpers import get_profile_image_urls_for_user
except ImportError:
    # This helper is not necessary when running tests because the
    # ChatXBlock._user_image_url method is patched
    pass


loader = ResourceLoader(__name__)


@XBlock.needs("i18n")
@XBlock.wants("user")
class ChatXBlock(StudioEditableXBlockMixin, XBlock):
    """
    An XBlock that allows learners to chat with a bot, where the bot
    follows a script and the learner can choose among possible
    responses.
    """

    display_name = String(
        display_name=_("Title (display name)"),
        help=_("Title to display"),
        default=_("Chat XBlock"),
        scope=Scope.content,
    )

    subject = String(
        display_name=_("Chat subject"),
        help=_("Subject being discussed in the chat"),
        default="",
        scope=Scope.content,
    )

    steps = String(
        display_name=_("Steps"),
        help=_(
            "Sequence of steps (in YAML). Each step is a mapping where the key represents the step id and "
            "whose value is a nested mapping with the following keys: 'messages' (sequence of strings), "
            "'image-url' (optional string), 'image-alt' (optional string), 'responses' (optional sequence "
            "of response mappings). In the response mappings the key represents the message displayed to "
            "the user as a response button and the value is the id of the next step."
        ),
        default=DEFAULT_DATA,
        multiline_editor=True,
        resettable_editor=False,
        scope=Scope.content,
    )

    bot_image_url = String(
        display_name=_("Bot profile image URL"),
        help=_(
            "For example, http://example.com/bot.png or /static/bot.png. "
            "In Studio, you can upload images from the Content - Files & Uploads page."
            "If using multiple bot personas, can be a YAML mapping of bot_id: image_url pairs."
        ),
        default='',
        multiline_editor=True,
        scope=Scope.content,
    )

    avatar_border_color = String(
        display_name=_("Avatar border color"),
        help=_(
            "Standard colors are #fdfe02 (yellow), #0000fe (blue), #ff551e (dark orange), #00ffff (cyan), "
            "#cccccc (grey), #fe0090 (fuchsia), #adff00 (lime), #fd9705 (light orange), #bf00fe (magenta), "
            "#39b54a (green)"
        ),
        scope=Scope.content,
    )

    enable_restart_button = Boolean(
        display_name=_("Enable restart button"),
        default=False,
        scope=Scope.content,
    )

    messages = List(
        help=_(
            "List of dictionaries representing the messages exchanged "
            "between the bot and the user. Each dictionary has the form: "
            "{'from': ..., 'message': '...', 'step': id}. The possible values for "
            "'from' are default_data.USER_ID, default_data.DEFAULT_BOT_ID, or a custom bot ID."
        ),
        scope=Scope.user_state,
        default=[],
    )

    current_step = String(
        help=(
            "Id of the current step the user has to take"
        ),
        scope=Scope.user_state,
    )

    editable_fields = (
        "display_name",
        "subject",
        "steps",
        "bot_image_url",
        "avatar_border_color",
        "enable_restart_button",
    )

    @staticmethod
    def resource_string(path):
        """Handy helper for getting resources from our kit."""
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def get_translation_content(self):
        try:
            language = utils.translation.get_language().split('-')
            if len(language) == 2:
                new_lang = language[0] + "_" + language[1]
            else:
                new_lang = utils.translation.get_language()
            return self.resource_string('public/js/translations/{lang}/textjs.js'.format(
                lang=new_lang,
            ))
        except IOError:
            return self.resource_string('public/js/translations/en/textjs.js')

    @XBlock.supports("multi_device")  # Mark as mobile-friendly
    def student_view(self, context=None):
        """View shown to students"""
        context = context.copy() if context else {}
        context["steps"] = self.steps
        fragment = Fragment()
        fragment.add_content(
            loader.render_django_template("templates/chat.html", context)
        )

        fragment.add_css_url(
            self.runtime.local_resource_url(self, "public/css/chat.css")
        )
        fragment.add_javascript_url(
            self.runtime.local_resource_url(
                self, "public/js/vendor/virtual-dom-1.3.0.min.js")
        )
        fragment.add_javascript(self.get_translation_content())
        fragment.add_javascript_url(
            self.runtime.local_resource_url(self, "public/js/src/chat.js")
        )
        fragment.initialize_js("ChatXBlock", self._js_init_data())
        return fragment

    def validate_field_data(self, validation, data):
        super(ChatXBlock, self).validate_field_data(validation, data)

        def add_error(msg):
            """ Helper function for adding validation messages. """
            validation.add(ValidationMessage(ValidationMessage.ERROR, msg))
        self._validate_steps(data.steps, add_error)

    def _validate_steps(self, steps, add_error):
        """
        Checks that the steps string can be decoded as a list.

        Then checks that each step dictionary in the list is valid.
        """
        steps = self._decode_steps_string(steps.strip())
        if steps is None:
            add_error(
                u"The Steps field has to be a YAML sequence of step mappings"
            )
        else:
            for step in steps:
                self._validate_step(step, add_error)

    @staticmethod
    def _decode_steps_string(steps):
        """Loads the string containing the list of steps."""
        try:
            steps = yaml.safe_load(steps)
        except yaml.parser.ParserError:
            steps = None
        if isinstance(steps, list):
            return steps

    @staticmethod
    def _missing_attributes(step, attributes):
        """Returns required keys missing in the step dictionary"""
        return [
            attribute for attribute in attributes
            if attribute not in step
        ]

    @property
    def _steps_as_list(self):
        """
        It replaces the NAME_PLACEHOLDER with the user's first name and
        returns steps as a list of dictionaries.
        """
        user_service = self.runtime.service(self, 'user')
        first_name = user_service.get_current_user().full_name.split(' ')[0]
        steps = self.steps.replace(NAME_PLACEHOLDER, first_name)
        steps = self._decode_steps_string(steps) or []
        return [self._normalize_step(step) for step in steps]

    @property
    def _steps_as_dict(self):
        """Returns a dictionary of steps like {step id: step, ...}"""
        return dict([
            (step["id"], step)
            for step in self._steps_as_list
        ])

    def _js_init_data(self):
        """Returns initialization JavaScript data for student view fragment"""
        steps = self._steps_as_dict
        first_step = steps[self._steps_as_list[0]["id"]] if steps else None
        return {
            "block_id": self._get_block_id(),
            "bot_image_urls": self._bot_image_urls(),
            "user_image_url": self._user_image_url(),
            "bot_sound_url": self.runtime.handler_url(
                self, 'serve_audio', 'bot.wav'),
            "response_sound_url": self.runtime.handler_url(
                self, 'serve_audio', 'response.wav'),
            "user_id": USER_ID,
            "anonymous_student_id": self._get_student_id(),
            "steps": steps,
            "first_step": first_step,
            "user_state": self._get_user_state(),
            "bot_message_animation_delay": BOT_MESSAGE_ANIMATION_DELAY,
            "user_message_animation_delay": USER_MESSAGE_ANIMATION_DELAY,
            "buttons_entering_transition_duration": BUTTONS_ENTERING_TRANSITION_DURATION,
            "buttons_leaving_transition_duration": BUTTONS_LEAVING_TRANSITION_DURATION,
            "scroll_delay": SCROLL_DELAY,
            "subject": self.subject,
            "avatar_border_color": self.avatar_border_color or None,
            "enable_restart_button": self.enable_restart_button,
            "typing_delay_per_character": TYPING_DELAY_PER_CHARACTER,
        }

    @staticmethod
    def _custom_bot_id(id):
        """Prefixes user-defined bot IDs so that they don't conflict with built-in DEFAULT_BOT_ID or USER_ID."""
        return 'custom/{}'.format(id)

    def _bot_image_urls(self):
        """Converts the value of bot_image_url field into a dict of bot_id: image_url key value pairs.
        If the value ia a dict, it adds an entry for the default bot image.
        If the value is a string, it assumes it represents the image url of the default bot."""
        mapping = {DEFAULT_BOT_ID: self._default_bot_image_url()}

        image_urls = yaml.safe_load(self.bot_image_url)
        if isinstance(image_urls, dict):
            for bot_id in image_urls:
                key = self._custom_bot_id(bot_id)
                mapping[key] = self._expand_static_url(image_urls[bot_id])
        elif isinstance(image_urls, basestring):
            mapping[DEFAULT_BOT_ID] = self._expand_static_url(image_urls)

        return mapping

    def _default_bot_image_url(self):
        """Returns the URL of the default bot image."""
        return self.runtime.local_resource_url(self, "public/bot.jpg")

    def _user_image_url(self):
        """Returns an image url for representing the learner in the chat"""
        user_service = self.runtime.service(self, 'user')
        user = user_service.get_current_user()
        username = user.opt_attrs.get('edx-platform.username')
        current_user = User.objects.get(username=username)  # pylint: disable=no-member
        urls = get_profile_image_urls_for_user(current_user)
        return urls.get('large')

    def _get_student_id(self):
        """Get student anonymous ID or normal ID"""
        if hasattr(self.runtime, 'anonymous_student_id'):
            return self.runtime.anonymous_student_id
        else:
            return self.scope_ids.user_id

    def _get_block_id(self):
        """
        Return unique ID of this block. Useful for HTML ID attributes.

        Works both in LMS/Studio and workbench runtimes:
        - In LMS/Studio, use the location.html_id method.
        - In the workbench, use the usage_id.
        """
        if hasattr(self, 'location'):
            return self.location.html_id()  # pylint: disable=no-member
        else:
            return str(self.scope_ids.usage_id)

    @XBlock.handler
    def get_user_state(self, request, suffix=""):
        """Returns JSON representing message exchanges and step to take"""
        data = self._get_user_state()
        return webob.Response(
            body=json.dumps(data), content_type='application/json'
        )

    def _get_user_state(self):
        """Returns the user fields state"""
        return {
            "messages": self.messages,
            "current_step": self.current_step,
        }

    def _is_final_step(self, step):
        """Returns true if current step doesn't exist or has no responses (is final step)."""
        steps_dict = self._steps_as_dict
        # Step with this ID does not exist, which means the chat is complete.
        if step not in steps_dict:
            return True
        # Step exists, but has no user responses available, which means this is the final step.
        if not steps_dict[step]['responses']:
            return True
        # Step exists and has responses for the user to choose from, so this is not the final step.
        return False

    @XBlock.json_handler
    def submit_response(self, data, suffix=''):
        """Saves the user state sent from the front end"""
        if len(data["messages"]) > len(self.messages):
            self.messages = data["messages"]
        self.current_step = data["current_step"]
        # Emit an event if chat is complete.
        if self._is_final_step(self.current_step):
            data = {'final_step': self.current_step}
            self.runtime.publish(self, 'xblock.chat.complete', data)
            self.runtime.publish(self, 'progress', {})

    @XBlock.json_handler
    def reset(self, data, suffix=''):
        """Resets chat state"""
        self.messages = []
        self.current_step = None

    @XBlock.handler
    def serve_audio(self, request, wav_name):
        """
        Serves wav audio file, respecting the Range header.
        Safari on OS X and iOS will not play audio files if the server does not respect Range requests.
        """
        if wav_name not in ['bot.wav', 'response.wav']:
            raise Http404('File does not exist')

        filepath = pkg_resources.resource_filename(__name__, 'public/{}'.format(wav_name))
        stat = os.stat(filepath)

        if request.range:
            content_range = request.range.content_range(length=stat.st_size)
            content_length = content_range.stop - content_range.start
            status = 206
        else:
            content_range = None
            content_length = stat.st_size
            status = 200

        with open(filepath, 'rb') as f:
            if (content_range):
                f.seek(content_range.start)
            body = f.read(content_length)

        response = webob.Response(
            body=body,
            status=status,
            content_type='audio/wav',
            content_length=content_length,
            content_range=content_range,
            last_modified=stat.st_mtime,
            content_disposition='attachment; filename="{}"'.format(wav_name),
        )

        return response

    @staticmethod
    def _as_yaml(step):
        """Encodes a step as a YAML object"""
        return yaml.dump(step).strip()

    @staticmethod
    def _is_valid_dict(step):
        """Checks if the YAML step is a dictionary and has a single key"""
        return (
            isinstance(step, dict) and
            len(list(step.keys())) == 1
        )

    def _validate_step(self, step, add_error):
        """
        Checks if the step is a dictionary with a single key.

        Then checks that its only value is a dictionary with a 'messages'
        key and an optional 'responses' key.

        A valid YAML step looks like this:

        - step1:
            messages: ["What is 1+1?", "What is the sum of 1 and 1?"]
            responses:
                - 2: step2
                - 3: step3
        """
        if not self._is_valid_dict(step):
            msg = (
                u"Step {step} must be a valid YAML mapping with "
                u"a string key and a nested mapping of 'messages' and "
                u"optional 'responses' as its value."
            )
            add_error(
                msg.format(
                    step=self._as_yaml(step)
                )
            )
            return
        content = list(step.values())[0]
        required_attributes = ["messages"]
        missing_attributes = self._missing_attributes(content, required_attributes)
        if missing_attributes:
            msg = (
                u"Step {step} is missing the following attributes: "
                u"{attributes}"
            )
            add_error(
                msg.format(
                    step=self._as_yaml(step),
                    attributes=u", ".join(missing_attributes),
                )
            )
        else:
            self._validate_messages(step, content["messages"], add_error)
            self._validate_responses(step, content.get("responses", []), add_error)
            self._validate_image_url(step, content.get("image-url"), add_error)
            self._validate_image_alt(step, content.get("image-alt"), add_error)

    def _validate_messages(self, step, messages, add_error):
        """Checks that messages is a string or a list of strings."""
        if not self._has_valid_messages(messages):
            msg = (
                u"The attribute 'messages' has to be a string or a list "
                u"of strings in {step}."
            )
            add_error(msg.format(step=self._as_yaml(step)))

    @staticmethod
    def _has_valid_messages(messages):
        """Checks that messages is a string or a list of strings."""
        return (
            isinstance(messages, basestring) or isinstance(messages, list)
        )

    def _validate_responses(self, step, responses, add_error):
        """
        Checks if 'responses' is a list of dictionaries containing a
        single key, used as response message and a single value which
        represents the id of the next step.

        A valid YAML response looks like this:

        responses:
            - Yes please: step1
            - No thanks: null

        Note that the 'responses' list may also be empty.
        """
        if not self._has_valid_responses(responses):
            msg = (
                u"The 'responses' attribute of {step} has to be a list "
                u"of response mappings of maximum length {max_length}."
            )
            add_error(
                msg.format(step=self._as_yaml(step), max_length=MAX_USER_RESPONSES)
            )
            return

    def _has_valid_responses(self, responses):
        """
        Checks if 'responses' is a list of up to MAX_USER_RESPONSES response
        dictionaries.

        Then checks if each response has a single key.
        """

        if not (isinstance(responses, list) and len(responses) <= MAX_USER_RESPONSES):
            return False
        return all(
            self._is_valid_yaml_response(response) for response in responses
        )

    @staticmethod
    def _is_valid_yaml_response(response):
        """Checks if the response dictionary has a single key."""
        return (
            isinstance(response, dict) and
            len(list(response.keys())) == 1
        )

    def _normalize_step(self, step):
        """
        Converts a step into a dictionary in the format expected by the frontend code.

        The format is:

        step = {
            "id": "step1",
            "messages": [
                [{"message": "How are you?", "bot_id": "bot"}],
                [{"message": "How are you doing?", "bot_id": "custom/other-bot"}],
                [{"message": "Hey", "bot_id": "bot"}, {"message": "How are you?", "bot_id": "custom/third-bot"}],
            ],
            "image_url": "http://example.com/image.png",
            "image_alt": "Alternative text for image.png",
            "responses": [
                {"message": "I'm OK", "step": "step2"},
                {"message": "I'm fine", "step": "step2"},
                {"message": "I'm great!", "step": "step2"},
            ],
        }
        """
        content = list(step.values())[0]
        messages = self._normalize_step_messages(content["messages"])
        return {
            "id": str(list(step.keys())[0]),
            "messages": messages,
            "image_url": content.get("image-url"),
            "image_alt": content.get("image-alt"),
            "notice_type": content.get("notice-type"),
            "notice_text": content.get("notice-text"),
            "responses": self._normalize_responses(content.get("responses", []))
        }

    @staticmethod
    def _normalize_responses(responses):
        """Normalizes a response dictionary."""
        return [
            {
                "message": str(list(response.keys())[0]),
                "step": str(list(response.values())[0]),
            }
            for response in responses
        ]

    def _normalize_step_message(self, step_message):
        """Converts a 'step_message' into a list of message objects with 'message' and 'bot_id' entries.

        The step_message may be a string, a dict with bot_id: message key value pairs, or a list
        containing strings and/or dicts.

        If the messages attribute is a string, it assumes the message belongs to the default bot."""

        result = []
        if isinstance(step_message, basestring):
            result.append({'message': step_message, 'bot_id': DEFAULT_BOT_ID})
        elif isinstance(step_message, dict):
            for key in step_message:
                bot_id = self._custom_bot_id(key)
                result.append({'message': step_message[key], 'bot_id': bot_id})
        elif isinstance(step_message, list):
            for message in step_message:
                result += self._normalize_step_message(message)
        return result

    def _normalize_step_messages(self, step_messages):
        """Converts the messages attribute into a list of lists. This is necessary for presenting
        multiple BOT messages in a row.

        If the message attribute is a simple value (string or dict), it only wraps the value in a list.
        If the messages attribute is a list, it wraps each value in a list.
        """
        result = []
        if isinstance(step_messages, list):
            for message in step_messages:
                result.append(self._normalize_step_message(message))
        else:
            result.append(self._normalize_step_message(step_messages))
        return result

    def _validate_image_url(self, step, image_url, add_error):
        """Checks that the image URL is a valid URL string"""
        if image_url is not None:
            validator = URLValidator()
            try:
                validator(image_url)
            except ValidationError:
                msg = (
                    u"The 'image-url' attribute of {step} has to be a valid URL string."
                )
                add_error(
                    msg.format(step=self._as_yaml(step))
                )

    def _validate_image_alt(self, step, image_alt, add_error):
        """Checks that the alternative text of the image is a string"""
        if image_alt is not None:
            if not isinstance(image_alt, basestring):
                msg = (
                    u"The 'image-alt' attribute of {step} has to be a string."
                )
                add_error(
                    msg.format(step=self._as_yaml(step))
                )

    def _expand_static_url(self, url):
        """
        This is required to make URLs like '/static/dnd-test-image.png' work (note: that is the
        only portable URL format for static files that works across export/import and reruns).
        This method is unfortunately a bit hackish since XBlock does not provide a low-level API
        for this.
        """
        if hasattr(self.runtime, 'replace_urls'):
            url = self.runtime.replace_urls('"{}"'.format(url))[1:-1]
        elif hasattr(self.runtime, 'course_id'):
            # edX Studio uses a different runtime for 'studio_view' than 'student_view',
            # and the 'studio_view' runtime doesn't provide the replace_urls API.
            try:
                from static_replace import replace_static_urls  # pylint: disable=import-error
                url = replace_static_urls('"{}"'.format(url), None, course_id=self.runtime.course_id)[1:-1]
            except ImportError:
                pass
        return url

    @XBlock.handler
    def chat_complete(self, request, suffix=""):
        """This is called from the front end when the learner has completed the chat."""
        # Does nothing at the moment; this HTTP request is listened for by some mobile apps
        # to trigger events after the chat is completed.
        return webob.Response()
