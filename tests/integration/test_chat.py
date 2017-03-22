import os
import pkg_resources
import yaml
import re

from ddt import ddt
from mock import ANY, patch

from django.test.client import Client

from bok_choy.promise import EmptyPromise
from xblock.reference.user_service import XBlockUser
from xblockutils.resources import ResourceLoader
from xblockutils.studio_editable_test import StudioEditableBaseTest

loader = ResourceLoader(__name__)

yaml_good = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

yaml_invalid_step = """
- step1
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

yaml_missing_messages = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    responses:
        - Yes please: step1
        - No thanks: null
"""

yaml_empty_messages = """
- step1:
    messages: []
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

yaml_invalid_responses = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    responses: ["response a", "response b"]
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

multiple_steps = """
- step1:
    messages:
    - ["What is 1+1?", "What is the sum of 1 and 1?", "1 + 1 is:", "1 plus 1 equals what?", "one + one?"]
    responses:
    - 2: step2
    - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
    - Yes please: step1
    - No thanks: null
"""

messages_lists = """
- step1:
    messages:
    - message step1.1
    - message step1.2
    - ["message step1.3.a", "message step1.3.b"]
    - message step1.4
    - ["message step1.5.a", "message step1.5.b", "message step1.5.c"]
    responses:
    - go back to step1: step1
    - finish: null
"""

invalid_image_url = """
- step1:
    messages:
    - ["What is 1+1?", "What is the sum of 1 and 1?", "1 + 1 is:", "1 plus 1 equals what?", "one + one?"]
    image-url: "This is not a valid URL"
    responses:
    - 2: step2
    - 3: step3
"""

invalid_image_alt = """
- step1:
    messages:
    - ["What is 1+1?", "What is the sum of 1 and 1?", "1 + 1 is:", "1 plus 1 equals what?", "one + one?"]
    image-url: "http://example.com/image.png"
    image-alt: [1, 2, 3]
    responses:
    - 2: step2
    - 3: step3
"""

valid_image_url = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    image-url: http://localhost/image.png
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

valid_image_alt = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    image-url: http://localhost/other.png
    image-alt: This is another image in localhost
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

name_placeholder = """
- step1:
    messages:
        - Hello [NAME], what is 1+1?
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job [NAME].
- step3:
    messages: Hmm, no [NAME], it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

real_image_url = """
- step1:
    messages:
        - ["What is 1+1?", "What is the sum of 1 and 1?"]
    image-url: http://localhost:8081/resource/chat/public/bot.jpg
    responses:
        - 2: step2
        - 3: step3
- step2:
    messages: Yep, that's correct! Good job.
- step3:
    messages: Hmm, no, it's not 3. (It's less.) Would you like to try again?
    responses:
        - Yes please: step1
        - No thanks: null
"""

yaml_final_steps = """
- 1:
    messages: What would you like to test?
    responses:
        - Response that points to non-existing step: 2
        - Response that points to existing step with no further responses: 3
- 2:
    messages: Alright! Clicking the response will complete the chat.
    responses:
        - OK: FINAL_STEP_MARKER
- 3:
    messages: Clicking the response will lead to a step with no further responses, completing the chat.
    responses:
        - OK: 4
- 4:
    messages: This is the final step, no further response available.
"""


@ddt
class TestChat(StudioEditableBaseTest):

    default_css_selector = 'div.chat-block'
    module_name = __name__

    def setUp(self):
        super(TestChat, self).setUp()
        def mocked_url(block):
            return '/static/images/profiles/default_120.png'
        patcher = patch('chat.chat.ChatXBlock._user_image_url', mocked_url)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Don't wait for bot message animations
        patcher = patch('chat.chat.BOT_MESSAGE_ANIMATION_DELAY', 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Don't wait for user message animations
        patcher = patch('chat.chat.USER_MESSAGE_ANIMATION_DELAY', 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        # Don't wait for buttons and scroll animations
        patcher = patch('chat.chat.BUTTONS_ENTERING_TRANSITION_DURATION', 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('chat.chat.BUTTONS_LEAVING_TRANSITION_DURATION', 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('chat.chat.SCROLL_DELAY', 0)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = patch('workbench.runtime.WorkbenchRuntime.replace_urls',
                        lambda _, html: re.sub(r'"/static/([^"]*)"', r'"/course/test-course/assets/\1"', html),
                        create=True,
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        # Don't wait for typing delay per character
        patcher = patch('chat.chat.TYPING_DELAY_PER_CHARACTER', 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def wait_until_buttons_are_displayed(self):
        self.wait_until_exists('div.buttons.entering')

    def wait_for_ajax(self, timeout=15):
        """
        Wait for jQuery to be loaded and for all ajax requests to finish.
        Same as bok-choy's PageObject.wait_for_ajax()
        """
        def is_ajax_finished():
            """ Check if all the ajax calls on the current page have completed. """
            return self.browser.execute_script("return typeof(jQuery)!='undefined' && jQuery.active==0")

        EmptyPromise(is_ajax_finished, "Finished waiting for ajax requests.", timeout=timeout).fulfill()

    def click_button(self, text):
        xpath_selector = '//button[contains(text(), "{}")]'.format(text)
        self.element.find_element_by_xpath(xpath_selector).click()

    def expect_error_message(self, expected_message):
        notification = self.dequeue_runtime_notification()
        self.assertEqual(notification[0], "error")
        self.assertEqual(notification[1]["title"], "Unable to update settings")
        self.assertEqual(notification[1]["message"], expected_message)

    def load_scenario(self, path, params=None):
        scenario = loader.render_template(path, params)
        self.set_scenario_xml(scenario)
        self.element = self.go_to_view("student_view")

    def test_serve_audio_handler(self):
        self.load_scenario("xml/chat_defaults.xml")
        block = self.load_root_xblock()
        filepath = pkg_resources.resource_filename('chat', 'public/response.wav')
        filesize = os.stat(filepath).st_size
        sound_url = block.runtime.handler_url(block, 'serve_audio', 'response.wav')
        client = Client()

        # Request without Range header works correctly.
        response = client.get(sound_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="response.wav"')
        self.assertEqual(response['Content-Length'], str(filesize))
        self.assertNotIn('Content-Range', response)
        self.assertEqual(len(response.content), filesize)

        # Request with Range header works correctly.
        # Request the first two bytes of the file (first/last byte in range hader are inclusive).
        response = client.get(sound_url, HTTP_RANGE='bytes=0-1')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Type'], 'audio/wav')
        self.assertEqual(response['Content-Disposition'], 'attachment; filename="response.wav"')
        self.assertEqual(response['Content-Length'], '2')
        self.assertEqual(response['Content-Range'], 'bytes 0-1/{}'.format(filesize))
        self.assertEqual(len(response.content), 2)

        # Request to non-existing file return 404.
        bad_file_url = block.runtime.handler_url(block, 'serve_audio', 'idontexist.wav')
        response = client.get(bad_file_url)
        self.assertEqual(response.status_code, 404)

    def test_defaults(self):
        self.load_scenario("xml/chat_defaults.xml")
        default_bot_messages = [
            "Hello there, would you like to chat about this XBlock?"
        ]
        default_response_labels = [
            "Yes, of course!",
            "No, not right now",
        ]
        self.wait_until_buttons_are_displayed()
        bot_message = self.element.find_element_by_css_selector(
            '.messages .message-body p').text
        self.assertIn(bot_message, default_bot_messages)
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, default_response_labels)

    def configure_block(self, yaml, expect_success=True, bot_image_url=None, avatar_border_color=None):
        self.load_scenario("xml/chat_defaults.xml")
        self.go_to_view("studio_view")
        self.fix_js_environment()
        control = self.get_element_for_field('steps')
        control.clear()
        control.send_keys(yaml)
        if bot_image_url is not None:
            control = self.get_element_for_field('bot_image_url')
            control.clear()
            control.send_keys(bot_image_url)
        if avatar_border_color is not None:
            control = self.get_element_for_field('avatar_border_color')
            control.clear()
            control.send_keys(avatar_border_color)
        self.click_save(expect_success)

    def test_steps_has_to_be_a_yaml_list(self):
        self.configure_block("hello", expect_success=False)
        self.expect_error_message(
            "The Steps field has to be a YAML sequence of step mappings"
        )

    def test_response_buttons(self):
        steps = loader.load_unicode('sample.yaml')
        self.configure_block(steps)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        step_a_response_labels = [u'a-to-b-1', u'a-to-b-2', u'a-to-c-1']
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, step_a_response_labels)
        # go to step b
        self.click_button('a-to-b-1')
        self.wait_until_buttons_are_displayed()
        step_b_response_labels = [u'b-to-d-1']
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, step_b_response_labels)
        # go to step d
        self.click_button('b-to-d-1')
        self.wait_until_buttons_are_displayed()
        step_d_response_labels = [u'd-to-f-1', u'd-to-g-1']
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, step_d_response_labels)
        # go to step f
        self.click_button('d-to-f-1')
        self.wait_until_buttons_are_displayed()
        step_f_response_labels = [u'f-to-h-1', u'f-to-i-1']
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, step_f_response_labels)
        # go to step i
        self.click_button('f-to-i-1')
        self.wait_until_buttons_are_displayed()
        step_i_response_labels = [u'Finish']
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector(
                    '.buttons .response-button button')
        ]
        self.assertEqual(button_labels, step_i_response_labels)

    def test_multiple_step_messages(self):
        value = [
            {
                "1": {
                    "messages": [["Hi", "How are you?"]],
                    "responses": [
                        {"Good!": "COMPLETE"},
                    ],
                },
            },
        ]
        self.configure_block(yaml.dump(value))
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        bot_message = self.element.find_element_by_css_selector(
            '.messages .bot .message-body p').text
        self.assertIn(bot_message, ["Hi", "How are you?"])

    def test_prefer_message_not_displayed(self):
        self.configure_block(multiple_steps)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        selector = '.messages .bot:last-child .message-body p'
        # save initial bot message
        first_bot_message = self.element.find_element_by_css_selector(selector).text
        # select wrong answer and try again
        self.click_button('3')
        self.wait_until_buttons_are_displayed()
        self.click_button('Yes please')
        # the second message displayed has to be different to the initial one
        self.wait_until_buttons_are_displayed()
        second_bot_message = self.element.find_element_by_css_selector(selector).text
        self.assertNotEqual(second_bot_message, first_bot_message)
        # select wrong answer and try again
        self.click_button('3')
        self.wait_until_buttons_are_displayed()
        self.click_button('Yes please')
        self.wait_until_buttons_are_displayed()
        # the third message displayed has to be different to the other two
        third_bot_message = self.element.find_element_by_css_selector(selector).text
        self.assertNotEqual(third_bot_message, first_bot_message)
        self.assertNotEqual(third_bot_message, second_bot_message)
        # select wrong answer and try again
        self.wait_until_buttons_are_displayed()
        self.click_button('3')
        self.wait_until_buttons_are_displayed()
        self.click_button('Yes please')
        self.wait_until_buttons_are_displayed()
        # the forth message displayed has to be different to the other three
        forth_bot_message = self.element.find_element_by_css_selector(selector).text
        self.assertNotEqual(forth_bot_message, first_bot_message)
        self.assertNotEqual(forth_bot_message, second_bot_message)
        self.assertNotEqual(forth_bot_message, third_bot_message)
        # I know, this test can be optimized... now the fifth
        self.wait_until_buttons_are_displayed()
        self.click_button('3')
        self.wait_until_buttons_are_displayed()
        self.click_button('Yes please')
        self.wait_until_buttons_are_displayed()
        fifth_bot_message = self.element.find_element_by_css_selector(selector).text
        self.assertNotEqual(fifth_bot_message, first_bot_message)
        self.assertNotEqual(fifth_bot_message, second_bot_message)
        self.assertNotEqual(fifth_bot_message, third_bot_message)
        self.assertNotEqual(fifth_bot_message, forth_bot_message)

    def test_empty_steps_list(self):
        self.configure_block("[]")
        self.element = self.go_to_view("student_view")
        messages = self.element.find_element_by_css_selector('div.messages')
        # No messages are displayed
        self.assertEqual(messages.get_attribute('innerHTML'), '')

    def test_yaml_script(self):
        self.configure_block(yaml_good)
        self.element = self.go_to_view("student_view")
        default_messages = ["What is 1+1?", "What is the sum of 1 and 1?"]
        bot_messages = self.element.find_elements_by_css_selector('.messages .message-body p')
        self.assertEqual(len(bot_messages), 1)
        bot_message = bot_messages[0]
        self.assertIn(bot_message.text, default_messages)
        button_labels = [
            label.text
            for label in self.element.find_elements_by_css_selector('.buttons .response-button button')
        ]
        self.assertEqual(button_labels, ["2", "3"])
        # click on 3
        self.click_button('3')
        bot_messages = ["Hmm, no, it's not 3. (It's less.) Would you like to try again?"]
        bot_message = self.element.find_elements_by_css_selector('.messages .message-body p')[-1].text
        self.assertIn(bot_message, bot_messages)

    def test_yaml_validation(self):
        # Test a step not being a dictionary
        self.configure_block(yaml_invalid_step, expect_success=False)
        self.expect_error_message(
            u"Step step1\n... must be a valid YAML mapping "
            u"with a string key and a nested mapping of 'messages' and "
            u"optional 'responses' as its value."
        )
        # Test a step with missing messages attribute
        self.configure_block(yaml_missing_messages, expect_success=False)
        self.expect_error_message(
            u"Step step3:\n  responses:\n  - {Yes please: step1}\n  "
            u"- {No thanks: null} is missing the following attributes: "
            u"messages"
        )
        # Test a step with its messages list being empty
        self.configure_block(yaml_empty_messages, expect_success=False)
        self.expect_error_message(
            u"The attribute 'messages' has to be a string or a "
            u"list of strings in step1:\n  messages: []\n  "
            u"responses:\n  - {2: step2}\n  - {3: step3}."
        )
        # Test a step with its responses list not containing dictionaries
        self.configure_block(yaml_invalid_responses, expect_success=False)
        self.expect_error_message(
            u"The 'responses' attribute of step1:\n  messages:\n  - ['What is 1+1?', "
            u"'What is the sum of 1 and 1?']\n  responses: [response a, response b] has to "
            u"be a list of response mappings."
        )

    def test_image_url_validation(self):
        self.configure_block(invalid_image_url, expect_success=False)
        self.expect_error_message(
            u"The 'image-url' attribute of step1:\n  image-url: This is not a valid URL\n  "
            u"messages:\n  - ['What is 1+1?', 'What is the sum of 1 and 1?', '1 + 1 is:', "
            u"'1 plus 1 equals\n      what?', 'one + one?']\n  responses:\n  - {2: step2}\n  - "
            u"{3: step3} has to be a valid URL string."
        )

    def test_image_alt_validation(self):
        self.configure_block(invalid_image_alt, expect_success=False)
        self.expect_error_message(
            u"The 'image-alt' attribute of step1:\n  image-alt: [1, 2, 3]\n  image-url: "
            u"http://example.com/image.png\n  messages:\n  - ['What is 1+1?', 'What is the sum of 1 and 1?', "
            u"'1 + 1 is:', '1 plus 1 equals\n      what?', 'one + one?']\n  responses:\n  - "
            u"{2: step2}\n  - {3: step3} has to be a string."
        )

    def test_image_rendering(self):
        self.configure_block(valid_image_url)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        selector = '.messages .bot .message-body p'
        bot_messages = self.element.find_elements_by_css_selector(selector)
        # The first message has an img element
        img = bot_messages[0].find_element_by_tag_name('img')
        # And the image has a valid URL
        self.assertEqual(img.get_attribute('src'), 'http://localhost/image.png')
        # The alternative text hasn't been defined for the step so it's empty
        self.assertEqual(img.get_attribute('alt'), '')

    def test_image_alternative_text(self):
        self.configure_block(valid_image_alt)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        selector = '.messages .bot .message-body p'
        bot_messages = self.element.find_elements_by_css_selector(selector)
        # The first message has an img element
        img = bot_messages[0].find_element_by_tag_name('img')
        # And the image has a valid URL and alternative text
        self.assertEqual(img.get_attribute('src'), 'http://localhost/other.png')
        self.assertEqual(img.get_attribute('alt'), 'This is another image in localhost')

    def test_image_in_history_is_displayed(self):
        self.configure_block(valid_image_alt)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        selector = '.messages .bot .message-body p'
        bot_messages = self.element.find_elements_by_css_selector(selector)
        # The first message has an img element
        img = bot_messages[0].find_element_by_tag_name('img')
        # And the image has a valid URL and alternative text
        self.assertEqual(img.get_attribute('src'), 'http://localhost/other.png')
        self.assertEqual(img.get_attribute('alt'), 'This is another image in localhost')
        # Select wrong answer and try again a few times
        for i in range(3):
            self.click_button('3')
            self.wait_until_buttons_are_displayed()
            self.click_button('Yes please')
            self.wait_until_buttons_are_displayed()
        # We have seven bot messages displayed by now
        bot_messages = self.element.find_elements_by_css_selector(selector)
        self.assertEqual(len(bot_messages), 7)
        # Let's reload the page to see the history
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        # We have the same seven bot messages displayed
        bot_messages = self.element.find_elements_by_css_selector(selector)
        self.assertEqual(len(bot_messages), 7)
        # And the first message contains the img element
        bot_messages = self.element.find_elements_by_css_selector(selector)
        img = bot_messages[0].find_element_by_tag_name('img')
        self.assertEqual(img.get_attribute('src'), 'http://localhost/other.png')
        self.assertEqual(img.get_attribute('alt'), 'This is another image in localhost')

    def test_image_overlay(self):
        self.configure_block(real_image_url)
        self.element = self.go_to_view('student_view')
        self.wait_until_buttons_are_displayed()
        image_overlays = self.element.find_elements_by_css_selector('.image-overlay')
        self.assertEqual(len(image_overlays), 0)
        image = self.element.find_element_by_css_selector('.message-body p img')
        # Clicking the image opens the overlay.
        image.click()
        image_overlays = self.element.find_elements_by_css_selector('.image-overlay')
        self.assertEqual(len(image_overlays), 1)
        image_overlay = image_overlays[0]
        zoomed_image = image_overlay.find_element_by_tag_name('img')
        self.assertEqual(zoomed_image.get_attribute('src'), image.get_attribute('src'))
        style = zoomed_image.get_attribute('style')
        self.assertIn('max-width: none', style)
        self.assertIn('max-height: none', style)
        self.assertIn('position: fixed', style)
        self.assertIn('width:', style)
        self.assertIn('height:', style)
        self.assertIn('top:', style)
        self.assertIn('left:', style)
        # Clicking anywhere on the overlay closes it.
        image_overlay.click()
        image_overlays = self.element.find_elements_by_css_selector('.image-overlay')
        self.assertEqual(len(image_overlays), 0)

    def test_messages_lists(self):
        self.configure_block(messages_lists)
        self.element = self.go_to_view("student_view")
        self.wait_until_buttons_are_displayed()
        selector = '.messages .bot .message-body p'
        bot_messages = self.element.find_elements_by_css_selector(selector)
        # There should be 5 messages displayed
        self.assertEqual(len(bot_messages), 5)
        # The messages text should be in the same order as the list items
        self.assertEqual(bot_messages[0].text, 'message step1.1')
        self.assertEqual(bot_messages[1].text, 'message step1.2')
        first_message_1_3 = bot_messages[2].text
        self.assertIn(first_message_1_3, ['message step1.3.a', 'message step1.3.b'])
        self.assertEqual(bot_messages[3].text, 'message step1.4')
        first_message_1_5 = bot_messages[4].text
        self.assertIn(first_message_1_5, ['message step1.5.a', 'message step1.5.b', 'message step1.5.c'])
        # Let's repeat step 1
        self.click_button('go back to step1')
        self.wait_until_buttons_are_displayed()
        # Since messages 1.3 and 1.5 have subitems in them they show different options the second time
        bot_messages = self.element.find_elements_by_css_selector(selector)
        self.assertEqual(bot_messages[5].text, 'message step1.1')
        self.assertEqual(bot_messages[6].text, 'message step1.2')
        second_message_1_3 = bot_messages[7].text
        self.assertIn(second_message_1_3, ['message step1.3.a', 'message step1.3.b'])
        self.assertNotEqual(first_message_1_3, second_message_1_3)
        self.assertEqual(bot_messages[8].text, 'message step1.4')
        second_message_1_5 = bot_messages[9].text
        self.assertIn(second_message_1_5, ['message step1.5.a', 'message step1.5.b', 'message step1.5.c'])
        self.assertNotEqual(first_message_1_5, second_message_1_5)

    def test_bot_image_static_url(self):
        self.configure_block(yaml_good, bot_image_url='/static/bot.png')
        self.element = self.go_to_view("student_view")
        bot_message = self.element.find_element_by_css_selector('.messages .message.bot')
        image = bot_message.find_element_by_tag_name('img')
        self.assertEqual(image.get_attribute('src'), 'http://localhost:8081/course/test-course/assets/bot.png')

    def test_bot_image_absolute_url(self):
        self.configure_block(yaml_good, bot_image_url='http://example.com/bot.png')
        self.element = self.go_to_view("student_view")
        bot_message = self.element.find_element_by_css_selector('.messages .message.bot')
        image = bot_message.find_element_by_tag_name('img')
        self.assertEqual(image.get_attribute('src'), 'http://example.com/bot.png')

    def test_avatar_border_color(self):
        self.configure_block(yaml_good, avatar_border_color='#00ffff')
        self.element = self.go_to_view("student_view")
        # Select a response to get the user's avatar
        self.click_button('3')
        # Get the avatar images for the three messages
        images = self.element.find_elements_by_css_selector('.messages .message .avatar img')
        # The images have the border-color set
        for image in images:
            self.assertEqual(image.get_attribute("style"), "border-color: rgb(0, 255, 255);")

    def mock_user_service(self):
        # Make user service to return a set full name for the user
        def mocked_get_current_user(block):
            return XBlockUser(
                is_current_user=True,
                emails=["user@example.com"],
                full_name="John Doe"
            )
        patcher = patch('workbench.runtime.WorkBenchUserService.get_current_user', mocked_get_current_user)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_name_placeholder(self):
        self.mock_user_service()
        self.configure_block(name_placeholder)
        self.element = self.go_to_view("student_view")
        bot_messages = self.element.find_elements_by_css_selector('.messages .message.bot')
        # The name placeholder is replaced with the user's full name
        self.assertEqual(bot_messages[-1].text, "Hello John, what is 1+1?")
        self.wait_until_buttons_are_displayed()
        self.click_button('3')
        bot_messages = self.element.find_elements_by_css_selector('.messages .message.bot')
        self.assertEqual(
            bot_messages[-1].text,
            "Hmm, no John, it's not 3. (It's less.) Would you like to try again?"
        )
        self.wait_until_buttons_are_displayed()
        self.click_button('Yes please')
        self.wait_until_buttons_are_displayed()
        self.click_button('2')
        bot_messages = self.element.find_elements_by_css_selector('.messages .message.bot')
        self.assertEqual(bot_messages[-1].text, "Yep, that's correct! Good job John.")

    def test_state_saved_to_local_storage(self):
        self.configure_block(yaml_good)
        self.element = self.go_to_view("student_view")
        # localStorage should be empty initially.
        self.assertEqual(self.browser.execute_script('return localStorage.length'), 0)
        # Select a response to trigger saving the state.
        self.click_button('2')
        # localStorage should now contain user state.
        self.assertEqual(self.browser.execute_script('return localStorage.length'), 1)
        key = self.browser.execute_script('return localStorage.key(0)')
        self.assertTrue(key.startswith('chat-xblock-'))
        state = self.browser.execute_script('return JSON.parse(localStorage.getItem("{}"))'.format(key))
        self.assertEqual(len(state['messages']), 2)
        self.assertEqual(state['current_step'], 'step2')

    def test_state_loaded_from_local_storage(self):
        def is_step2_visible():
            """ Helper function that checks whether message from step2 is displayed. """
            step2_message = "Yep, that's correct! Good job."
            step2_selector = '//p[contains(text(), "{}")]'.format(step2_message)
            elements = self.element.find_elements_by_xpath(step2_selector)
            return len(elements) > 0

        self.configure_block(yaml_good)
        self.element = self.go_to_view("student_view")
        # Before clicking the button, we should not see message from step2:
        self.assertFalse(is_step2_visible())
        # Select a response to trigger saving the state.
        self.click_button('2')
        # We should now see the message from step2.
        self.assertTrue(is_step2_visible())
        # Patch the _get_user_state method to return a blank state.
        with patch('chat.chat.ChatXBlock._get_user_state') as mock_state:
            mock_state.return_value = {'messages': [], 'current_step': None}
            # Reload the page.
            self.element = self.go_to_view('student_view')
            # Observe that we can still see message from step2 after reload
            # (state was loaded from localStorage).
            self.assertTrue(is_step2_visible())
            # Observe that upon clearing localStorage and reloading the page,
            # step2 is no longer visible.
            self.browser.execute_script('localStorage.clear()')
            self.element = self.go_to_view('student_view')
            self.assertFalse(is_step2_visible())

    @patch('workbench.runtime.WorkbenchRuntime.publish')
    def test_complete_event_emitted_with_non_existing_step(self, mock_publish):
        self.configure_block(yaml_final_steps)
        self.element = self.go_to_view('student_view')
        self.click_button('Response that points to non-existing step')
        self.assertFalse(mock_publish.called)
        self.click_button('OK')
        self.wait_for_ajax()
        mock_publish.assert_called_with(ANY, 'xblock.chat.complete', {'final_step': 'FINAL_STEP_MARKER'})

    @patch('workbench.runtime.WorkbenchRuntime.publish')
    def test_complete_event_emitted_with_step_without_responses(self, mock_publish):
        self.configure_block(yaml_final_steps)
        self.element = self.go_to_view('student_view')
        self.click_button('Response that points to existing step with no further responses')
        self.assertFalse(mock_publish.called)
        self.click_button('OK')
        self.wait_for_ajax()
        mock_publish.assert_called_with(ANY, 'xblock.chat.complete', {'final_step': '4'})
