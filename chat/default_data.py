"""Default data for Chat XBlock"""


DEFAULT_DATA = """- 1:
    messages: Hello there, would you like to chat about this XBlock?
    responses:
    - Yes, of course!: 3
    - No, not right now: 2
- 2:
    messages:
    - OK, maybe another time then.
    - Have a nice day!
    responses:
    - Bye!: COMPLETE
- 3:
    messages:
    - Great!
    - Would you like to know my name first?
    responses:
    - 'Yes': 4
    - 'No': 5
- 4:
    messages:
    - My name is Bot. And I believe you are [NAME].
    responses:
    - Nice to meet you!: 5
    - That is not my name.: 5
- 5:
    messages:
    - Would you like to learn how to use this XBlock?
    responses:
    - Yes, please!: 6
    - 'No': 2
- 6:
    messages:
    - It's easy!
    - It's all in the README!
"""

BOT_ID = 'bot'
USER_ID = 'user'
BOT_MESSAGE_ANIMATION_DELAY = 2500
USER_MESSAGE_ANIMATION_DELAY = 1000
BUTTONS_ENTERING_TRANSITION_DURATION = 1000
BUTTONS_LEAVING_TRANSITION_DURATION = 800
SCROLL_DELAY = 800
NAME_PLACEHOLDER = '[NAME]'
TYPING_DELAY_PER_CHARACTER = 25
