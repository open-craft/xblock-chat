Chat XBlock
===========

An XBlock that allows learners to chat with a bot, where the bot follows
a script and the learner can choose among possible responses.

Authors define the script as a set of "steps".

The steps list can be defined as a YAML sequence of mappings whose key represents
the step id and the value is a nested mapping with messages and optional responses.
It's also possible to add an optional image (with alternative text) to the step.

A valid YAML steps sequence looks like this:

```yaml
- step1:
    messages: ["What is 1+1?", "What is the sum of 1 and 1?"]
    image-url: http://localhost/sum.png
    image-alt: Graphic representation of this sum
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
```


Installation
------------

Install the requirements into the Python virtual environment of your
`edx-platform` installation by running the following command from the
root folder:

```bash
$ pip install -r requirements.txt
```

Enabling in Studio
------------------

You can enable the Chat XBlock in Studio through the Advanced
Settings.

1. From the main page of a specific course, navigate to `Settings ->
   Advanced Settings` from the top menu.
2. Check for the `Advanced Module List` policy key, and add
   `"chat"` to the policy value list.
3. Click the "Save changes" button.


Testing
-------

Inside a fresh virtualenv, `cd` into the root folder of this repository
(`xblock-chat`) and run

```bash
$ pip install -r requirements-test.txt
$ pip install -r $VIRTUAL_ENV/src/xblock-sdk/requirements/base.txt
$ pip install -r $VIRTUAL_ENV/src/xblock-sdk/requirements/test.txt
$ pip install -r $VIRTUAL_ENV/src/xblock/requirements.txt
```

You can then run the entire test suite via

```bash
$ python run_tests.py
```


Necessary changes
-----------------

1. This XBlock displays the profile image of the user in the chat interface. For this feature to work on a devstack, it's necessary to add:

```python
MEDIA_ROOT = '/edx/var/edxapp/media'
```

to `edx-platform/lms/envs/private.py`

2. In order to make the chat interface responsive it's necessary to apply [this fix](https://github.com/open-craft/edx-platform/commit/2a1cf699452ae567bcb3caeb507760f29f1df830) to the LMS chromeless courseware template.
