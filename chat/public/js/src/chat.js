/* Javascript for ChatXBlock. */

function ChatTemplates(init_data) {
    "use strict";

    // A spacer div at the bottom of the screen is required on the iOS app to account for the prev/next toolbar.
    var SPACER_HEIGHT = 44;

    var h = virtualDom.h;

    var renderCollection = function(template, collection, ctx) {
        return collection.map(function(item) {
            return template(item, ctx);
        });
    };

    var imageTemplate = function(step) {
        var attributes = {
            'src': step.image_url,
            'alt': step.image_alt || ''
        };
        return (
            h('img', attributes)
        );
    };

    var noticeTemplate = function(step) {
      var tag = 'div.notice';

      if (step.notice_type) {
        tag = tag.concat('.' + step.notice_type);
      }

      return h(tag, h('p', step.notice_text));
    };

    var subjectTemplate = function(ctx) {
      if (ctx.subject) {
        return h('div.subject', h('p', ctx.subject));
      } else {
        return null;
      }
    };

    // Position the image to make it cover the max possible area of the window while
    // maintaining the aspect-ratio and keeping the entire image visible.
    // If image is landscape, but window orientation is vertical (or the other way around),
    // rotate the image 90 degrees.
    var optimalOverlayImageStyle = function(img_width, img_height, win_width, win_height) {
        var style = {
            'position': 'fixed',
            'max-width': 'none',
            'max-height': 'none'
        };

        var scale = Math.min(win_width/img_width, win_height/img_height);

        // Fitting a landscape image into a portrait-shaped window, or the other way around;
        // we have to rotate the image and recalculate the scale with swapped width & height.
        if ((img_width < img_height) !== (win_width < win_height)) {
            scale = Math.min(win_height/img_width, win_width/img_height);
            style['transform'] = 'rotate(90deg)';
        }

        var width = Math.floor(img_width * scale);
        var height = Math.floor(img_height * scale);

        style['width'] = width + 'px';
        style['height'] = height + 'px';
        style['top'] = Math.round((win_height - height) / 2) + 'px';
        style['left'] = Math.round((win_width - width) / 2) + 'px';

        return style;
    };

    var imageOverlayTemplate = function(ctx) {
        var src = ctx.image_overlay.image_url;
        var alt = ctx.image_overlay.image_alt;
        var img_dims = ctx.image_dimensions[src];
        var img_style = {};
        if (img_dims) {
            var win_width = $(window).width();
            var win_height = $(window).height() - SPACER_HEIGHT;
            img_style = optimalOverlayImageStyle(img_dims.width, img_dims.height, win_width, win_height);
        }
        return (
            h('div.image-overlay', [
                h('img', {src: src, alt: alt, style: img_style})
            ])
        );
    };

    var avatarTemplate = function(image_url) {
        var image_attributes = {
            'src': image_url
        };
        if (init_data["avatar_border_color"]) {
            image_attributes["style"] = {
                "border-color": init_data["avatar_border_color"]
            };
        }
        return (
            h('div.avatar', [
                h('img', image_attributes)
            ])
        );
    };

    var botMessageContentTemplate = function(bot_id, tag, children) {
        return (
            h(tag, [
                avatarTemplate(init_data['bot_image_urls'][bot_id]),
                h('div.message-body', [
                    h('p', children)
                ])
            ])
        );
    };

    var botMessageTemplate = function(message, extra_css_class) {
        var tag = 'div.message.bot';
        var children = [message.message];
        var step = init_data["steps"][message.step];
        if (step && step.image_url) {
            children = [imageTemplate(step), message.message];
        }

        if (extra_css_class) {
            tag = tag.concat('.' + extra_css_class);
        }
        var messageContent = botMessageContentTemplate(
          message.from, tag, children
        );

        if (step && step.notice_text) {
          return [noticeTemplate(step), messageContent];
        } else {
          return messageContent;
        }
    };

    var spinnerTemplate = function(bot_id) {
        var tag = 'div.message.bot.spinner-message';
        var spinner = [
            h('div.spinner', [
                h('div.bounce1'),
                h('div.bounce2'),
                h('div.bounce3')
            ])
        ];
        return botMessageContentTemplate(bot_id, tag, spinner);
    };

    var userMessageTemplate = function(message, extra_css_class) {
        var tag = 'div.message.user';
        if (extra_css_class) {
            tag = tag.concat('.' + extra_css_class);
        }
        return (
            h(tag, [
                h('div.message-body', [
                    h('p', message.message)
                ]),
                avatarTemplate(init_data['user_image_url'])
            ])
        );
    };

    var messagesTemplate = function(ctx) {
        var templates = {};
        templates[init_data["user_id"]] = userMessageTemplate;
        Object.keys(init_data["bot_image_urls"]).forEach(function(bot_id) {
            templates[bot_id] = botMessageTemplate;
        });
        var messages = [];
        ctx.messages.forEach(function(message) {
            if (message.from in templates) {
                messages.push(templates[message.from](message));
            }
        });
        if (ctx.bot_spinner) {
            messages.push(spinnerTemplate(ctx.bot_spinner.bot_id));
        } else if (ctx.new_bot_message) {
            messages.push(botMessageTemplate(ctx.new_bot_message, 'fadein-message'));
        } else if (ctx.new_user_message) {
            messages.push(userMessageTemplate(ctx.new_user_message, 'fadein-message'));
        }
        return (
            h(
                'div.messages',
                messages
            )
        );
    };

    var buttonTemplate = function(item, ctx) {
        var attributes = {
            'data-message': JSON.stringify(item.message),
            'data-step_id': JSON.stringify(item.step)
        };
        return (
            h(
                'div.response-button',
                {
                    attributes: attributes
                },
                [
                    h(
                        'button',
                        item.message
                    )
                ]
            )
        );
    };

    var buttonsTemplate = function(ctx, extra_css_class, transition_duration) {
        var tag = 'div.buttons';
        if (extra_css_class) {
            tag = tag.concat('.' + extra_css_class);
        }
        var attributes = {};
        if (transition_duration) {
            attributes = {
                style: {
                    transition: 'max-height '+ transition_duration + 'ms linear'
                }
            };
        }
        var step = ctx.current_step && init_data["steps"][ctx.current_step];
        if (step && step.responses.length) {
            return (
                h(
                    tag,
                    attributes,
                    renderCollection(
                        buttonTemplate,
                        step.responses,
                        ctx
                    )
                )
            );
        } else {
            return null;
        }
    };

    var actionsTemplate = function() {
        var children = [];
        if (init_data['enable_restart_button']) {
            children.push(h('button.restart-button', 'Restart'));
        }
        return h('div.actions', children);
    };

    var spacerTemplate = function() {
        return (
            h('div.spacer', {style: {height: SPACER_HEIGHT + 'px'}})
        );
    };

    var mainTemplate = function(ctx) {
        var children = [
            subjectTemplate(ctx),
            messagesTemplate(ctx)
        ];
        if (ctx.show_buttons) {
            if (ctx.show_buttons_entering) {
                children.push(buttonsTemplate(ctx, 'entering', init_data["buttons_entering_transition_duration"]));
            } else if (ctx.show_buttons_leaving) {
                children.push(buttonsTemplate(ctx, 'leaving', init_data["buttons_leaving_transition_duration"]));
            } else {
                children.push(buttonsTemplate(ctx));
            }
            children.push(actionsTemplate());
        }
        children.push(spacerTemplate());
        if (ctx.image_overlay) {
            children.push(imageOverlayTemplate(ctx));
        }
        return h('div.chat-block', children);
    };

    return mainTemplate;
}

function ChatXBlock(runtime, element, init_data) {
    "use strict";

    var renderView = ChatTemplates(init_data);

    var $element = $(element);
    var element = $element[0];
    var $root = $element.find('.chat-block');
    var root = $root[0];

    var __vdom = virtualDom.h();

    var bot_sound = new Audio(init_data["bot_sound_url"]);
    var response_sound = new Audio(init_data["response_sound_url"]);
    bot_sound.preload = true;
    response_sound.preload = true;

    var last_sound_played;

    /**
     * localStorageKey: returns a key under which state for this block instance
     * is stored in localStorage.
     */
    var localStorageKey = function() {
        return 'chat-xblock-' + init_data["block_id"];
    };

    /**
     * getStateFromLocalStorage: returns state saved in local storage, or null if it does not exist.
     */
    var getStateFromLocalStorage = function() {
        var key = localStorageKey();
        var state = null;
        try {
            state = localStorage.getItem(key);
        } catch (e) {
            // Fetching state from local storage will fail if localStorage is not available,
            // or if browser settings forbid access to localStorage.
            // Return null in that case.
            return null;
        }
        return JSON.parse(state);
    };

    /**
     * saveStateToLocalStorage: stores state to local storage. Ignores errors.
     */
    var saveStateToLocalStorage = function(serialized_state) {
        var key = localStorageKey();
        try {
            localStorage.setItem(key, serialized_state);
        } catch (e) {
            // Storing state to local storage will fail if localStorage is not available,
            // or if browser settings forbid access to localStorage.
            // There is nothing we can do about that, so just ignore the error.
        }
    };

    /**
     * clearLocalStorage: removes any state that this block stored to local storage.
     */
    var clearLocalStorage = function() {
        var key = localStorageKey();
        try {
            localStorage.removeItem(key);
        } catch (e) {
            // Accessing local storage will fail if localStorage is not available,
            // or if browser settings forbid access to localStorage.
            // We can safely ignore that error.
        }
    };

    /**
     * pause: delays execution with a timeout
     */
    var pause = function(timeout) {
        return new Promise(function(resolve, reject) {
            setTimeout(resolve, timeout);
        });
    };

    /**
     * init: loads audio and image resources in the background
     * and sets the initial state of the app based on the
     * user data passed from the backend
     */
    var init = function() {
        // prevent rubber band effect (overscroll) in iOS app
        if ($('.course-wrapper.chromeless').length) {
            $('html, body').css({
                position: 'fixed',
                overflow: 'hidden'
            });
        }
        $element.on('click', '.response-button', submitResponse);
        $element.on('click', '.restart-button', restartChat);
        $element.on('click', '.message-body img', showImageOverlay);
        $element.on('click', '.image-overlay', closeImageOverlay);
        var init_state = getStateFromLocalStorage() || init_data["user_state"];
        var state = initializeAndApplyState(init_state);
        // Try to load state from local storage and fall back to init_data.
        // Some mobile apps expect the chat_complete handler to be invoked
        // every time when loading the block if block is in complete state.
        pingHandlerIfComplete(state);
        return state;
    };

    /**
     * initializeAndApplyState: given initial state object, sets default values and applies the state.
     */
    var initializeAndApplyState = function(state) {
        state.current_step = initialStep(state);
        state = addBotMessages(state);
        state.scroll_delay = 0;
        state.image_overlay = null;
        state.image_dimensions = {};
        preloadImages();
        applyState(state);
        state.scroll_delay = init_data["scroll_delay"];
        state.subject = init_data["subject"];
        return state;
    };

    /**
     * preloadImages: preload all images used in this block and store their dimensions.
     */
    var preloadImages = function() {
        loadImage(init_data["user_image_url"]);
        Object.keys(init_data["bot_image_urls"]).forEach(function(bot_id) {
            loadImage(init_data["bot_image_urls"][bot_id]);
        });
        Object.keys(init_data["steps"]).forEach(function(step_id) {
            if (init_data["steps"][step_id].image_url) {
                loadImage(init_data["steps"][step_id].image_url);
            }
        });
    };

    /**
     * loadImage: helper to load an image in the background
     */
    var loadImage = function(url) {
        var promise = $.Deferred();
        var result = new Image();
        result.addEventListener("load", function() {
            state.image_dimensions[url] = {
                width: result.naturalWidth,
                height: result.naturalHeight
            };
            promise.resolve(result);
        }, false);
        result.addEventListener("error", function() {
            promise.reject();
        }, false);
        result.src = url;
        return promise;
    };

    /**
     * playSound: plays a sound and sets it as the last sound played
     */
    var playSound = function(sound) {
        sound.pause();
        sound.muted = false;
        sound.loop = false;
        // Only set currentTime if the sound has finished loading, otherwise some versions of FF
        // throw an error (see bug https://bugzilla.mozilla.org/show_bug.cgi?id=1188887)
        if (sound.readyState === 4) {
            // Some versions of FF may still throw InvalidStateError when trying to set currentTime
            // in some cases, so wrap it in a try/catch.
            try {
                sound.currentTime = 0;
            } catch (e) {
                // ignore
            }
        }
        sound.play();
        last_sound_played = sound;
    };

    /**
     * playSoundInMutedLoop: Mobile Safari will only play sounds when initiated
     * from event handlers resulting from direct user interaction.
     * Since our "bot" sound needs to play after the user chooses a response,
     * but not immediately on click/tap, we use a little trick to force Mobile Safari
     * to play the sound at the right time - we start playing the sound muted in loop mode
     * directly in the event handler, and then at the appropriate time unmute the sound,
     * stop the loop and let it play unmuted (using playSound above).
     */
    var playSoundInMutedLoop = function(sound) {
        sound.muted = true;
        sound.loop = true;
        sound.play();
    };

    /**
     * createMessageFromSender: returns an object that can be added to
     * the chat history on behalf of the sender (bot or user)
     */
    var createMessageFromSender = function(message, sender_id, step_id) {
        return {
            from: sender_id,
            message: message,
            step: step_id
        };
    };

    /**
     * showButtons: renders available user responses
     */
    var showButtons = function(state) {
        state.show_buttons = true;
        applyState(state);
        state.show_buttons_entering = true;
        applyState(state);
    };

    /**
     * hideButtons: sets css class on the buttons container to trigger the css transition
     */
    var hideButtons = function() {
        state.show_buttons_entering = false;
        state.show_buttons_leaving = true;
        state.new_user_message = null;
        applyState(state);
    };

    /**
     * waitForButtonsHiding: sets a pause while the css transition for hiding the buttons container takes place
     */
    var waitForButtonsHiding = function() {
        return pause(init_data["buttons_leaving_transition_duration"]);
    };

    /**
     * createUserMessage: removes the buttons container and creates the new user message
     * triggering the fadein css animation
     */
    var createUserMessage = function(event) {
        return function() {
            var $response = $(event.target).closest('.response-button');
            var message = JSON.parse($response.attr('data-message'));
            var step = state.current_step;
            state.new_user_message = createMessageFromSender(message, init_data["user_id"], step);
            state.show_buttons = false;
            state.show_buttons_leaving = false;
            applyState(state);
        };
    };

    /**
     * waitUserMessageAnimation: sets a pause for each animation on a new user message
     * (one for the message fading in and one for the message being displayed normally in the chat history)
     */
    var waitUserMessageAnimation = function() {
        var user_message_animations = 2;
        var delay_split = init_data["user_message_animation_delay"] / user_message_animations;
        return pause(delay_split);
    };

    /**
     * addUserMessageToHistory: adds the new user message to the chat history
     */
    var addUserMessageToHistory = function(event) {
        return function() {
            var $response = $(event.target).closest('.response-button');
            var step_id = JSON.parse($response.attr('data-step_id'));
            state.messages.push(state.new_user_message);
            state.new_user_message = null;
            state.current_step = step_id;
            applyState(state);
        };
    };

    /**
     * isFinalStep: returns true if current step doesn't exist or has no responses.
       This is the JS equivalent of the _is_final_step method of the XBlock.
     */
    var isFinalStep = function(step) {
        var steps_dict = init_data["steps"];
        // Step with this ID does not exist, which means the chat is complete.
        if (!(step in steps_dict)) {
            return true;
        }
        // Step exists, but has no user responses available, which means this is the final step.
        if (steps_dict[step].responses.length == 0) {
            return true;
        }
        // Step exists and has responses for the user to choose from, so this is not the final step.
        return false;
    };

    /**
    * Sends a GET request to the chat_complete handler if we are on final step.
    */
    var pingHandlerIfComplete = function(state) {
        if (isFinalStep(state.current_step)) {
            $.ajax({
                type: 'GET',
                url: runtime.handlerUrl(element, "chat_complete")
            });
        }
    };

    /**
     * saveState: stores state to localStorage and sends it to the server.
     */
    var saveState = function() {
        var serialized_state = JSON.stringify({
            messages: state.messages,
            current_step: state.current_step
        });
        // Save to localStorage.
        saveStateToLocalStorage(serialized_state);
        // Submit state to backend.
        $.ajax({
            type: 'POST',
            url: runtime.handlerUrl(element, "submit_response"),
            data: serialized_state
        });
        // If it's the final step ping the chat_complete handler
        pingHandlerIfComplete(state);
    };

    /**
     * restartChat: reset chat state and start from beginning.
     */
    var restartChat = function() {
        clearLocalStorage();
        $.ajax({
            type: 'POST',
            url: runtime.handlerUrl(element, 'reset'),
            data: '{}'
        });
        state = initializeAndApplyState({
            messages: [],
            current_step: null
        });
    };

    /**
     * addNewBotMessages: adds bot messages after the users' response has been submitted
     */
    var addNewBotMessages = function(state) {
        return function() {
            addBotMessages(state);
        };
    };

    /**
     * submitResponse: event handler for clicking a response button. Gets data attributes
     * from the button and adds the response and new bot messages to the chat history
     * setting pauses and fade animations in between
     */
    var submitResponse = function(event) {
        var promise;
        playSound(response_sound);
        playSoundInMutedLoop(bot_sound);
        promise = new Promise(function(resolve, reject) {
            resolve();
        }).then(hideButtons)
          .then(waitForButtonsHiding)
          .then(createUserMessage(event))
          .then(waitUserMessageAnimation)
          .then(addUserMessageToHistory(event))
          .then(waitUserMessageAnimation)
          .then(saveState)
          .then(addNewBotMessages(state));
    };

    var showImageOverlay = function(event) {
        var img = event.currentTarget;
        state.image_overlay = {
            image_url: img.src,
            image_alt: img.alt
        };
        applyState(state);
    };

    var closeImageOverlay = function(event) {
        state.image_overlay = null;
        applyState(state);
    };

    /**
     * applyState: patches the DOM and sets a new chat block based on the passed state.
     * It also animates the transition
     */
    var applyState = function(state) {
        var new_vdom = render(state);
        var patches = virtualDom.diff(__vdom, new_vdom);
        root = virtualDom.patch(root, patches);
        $root = $(root);
        animate(state);
        __vdom = new_vdom;
    };

    /**
     * animate: scrolls to the last message displayed and plays the bot sound
     * if there are response buttons and the bot sound wasn't the last played
     */
    var animate = function(state) {
        var $messages = $root.find('.messages');
        if (!state.scroll_delay) {
            $messages.scrollTop($messages.prop("scrollHeight"));
        } else if (state.bot_spinner || (state.show_buttons && !state.show_buttons_leaving) || state.new_user_message) {
            $messages.animate(
                {scrollTop: $messages.prop("scrollHeight")},
                {duration: state.scroll_delay, queue: false});
        }
        if (last_sound_played != bot_sound && $root.find('.bot.fadein-message').length) {
            playSound(bot_sound);
        }
    };

    /**
     * filterNotDisplayed: returns bot messages that have not been displayed in the chat yet.
     */
    var filterNotDisplayed = function(messages, displayed_messages) {
        return messages.filter(function(message) {
            var is_displayed = displayed_messages.some(function(displayed_message) {
                var messages_match = displayed_message.message === message.message;
                var senders_match = displayed_message.from === message.bot_id;
                return messages_match && senders_match;
            });
            return !is_displayed;
        });
    };

    /**
     * stepMessages: returns a message object for each step.messages item in the list.
     * If the item contains more than one element, it tries to randomly select messages still
     * not displayed by the bot in the history
     */
    var stepMessages = function(step, displayed_messages) {
        var result = [];
        var messages_not_displayed;
        var candidate_messages;
        var message_index;
        if (step && step.messages.length) {
            step.messages.forEach(function(messages) {
                messages_not_displayed = filterNotDisplayed(messages, displayed_messages);
                if (messages_not_displayed.length) {
                    candidate_messages = messages_not_displayed;
                } else {
                    candidate_messages = messages;
                }
                message_index = Math.floor(Math.random() * candidate_messages.length);
                result.push(candidate_messages[message_index]);
            });
        }
        return result;
    };

    /**
     * initialStep: if no messages have been exchanged yet returns the first step.
     * It also verifies that the current step is a valid step. If the current step
     * is not in the list of steps anymore (maybe it was deleted or changed), the UI
     * should just display the chat history
     */
    var initialStep = function(state) {
        var result;
        var first_step = init_data["first_step"];
        if (!state.messages.length && first_step) {
            result = first_step.id;
        } else if (state.current_step in init_data["steps"]) {
            result = state.current_step;
        };
        return result;
    };

    /**
     * lastMessageSender: returns the sender id of the last message in the chat
     */
    var lastMessageSender = function(oldState) {
        return oldState.messages[oldState.messages.length - 1].from;
    };

    /**
     * showSpinner: shows the ... spinner before adding a bot message to the chat
     */
    var showSpinner = function(state, bot_id) {
        return function() {
            state.bot_spinner = {bot_id: bot_id};
            state.new_bot_message = null;
            applyState(state);
        };
    };

    /**
     * waitBotMessageAnimation: sets a pause for each animation on a new bot message
     * (one for the spinner and one for the message being displayed normally in the chat history).
     * If a message is passed an extra delay is added to the pause based on the message length
     */
    var waitBotMessageAnimation = function(message) {
        var typing_delay_per_character = 0;
        var bot_message_animations = 2;
        var delay_split = init_data["bot_message_animation_delay"] / bot_message_animations;
        if (message) {
            typing_delay_per_character = message.length * init_data["typing_delay_per_character"];
        }
        return function() {
            return pause(delay_split + typing_delay_per_character);
        };
    };

    /**
     * createBotMessage: hides the ... spinner and creates the new message with a fade in animation
     */
    var createBotMessage = function(state, bot_id, message, step) {
        return function() {
            state.bot_spinner = null;
            state.new_bot_message = createMessageFromSender(message, bot_id, step.id);
            applyState(state);
        };
    };

    /**
     * addBotMessageToHistory: adds the new bot message to the chat history and if it's the last
     * message in the step shows the response buttons
     */
    var addBotMessageToHistory = function(state, is_last_message_in_step) {
        return function() {
            state.bot_spinner = null;
            state.messages.push(state.new_bot_message);
            state.new_bot_message = null;
            if (is_last_message_in_step) {
                showButtons(state);
            } else {
                applyState(state);
            }
        };
    };

    /**
     * addBotMessages: checks if the bot was not the last sending messages and then
     * adds each step message first to a temporary typing attribute and then to the
     * chat history pausing execution between renderings
     */
    var addBotMessages = function(oldState) {
        var promise;
        var step = init_data["steps"][oldState.current_step];
        var step_messages = stepMessages(step, oldState.messages);
        // If the bot was the last sending messages
        // and the messages selected from the step are the same
        // do nothing
        if (oldState.messages.length &&
            init_data["bot_image_urls"].hasOwnProperty(lastMessageSender(oldState))) {
            return oldState;
        }
        if (step_messages.length) {
            promise = new Promise(function(resolve, reject) {
                resolve();
            });
            step_messages.reduce(function(acc_promise, step_message, index, array) {
                var message = step_message.message;
                var bot_id = step_message.bot_id;
                var is_last_message_in_step = index === (step_messages.length - 1);
                return acc_promise
                    .then(showSpinner(oldState, bot_id))
                    .then(waitBotMessageAnimation(message))
                    .then(createBotMessage(oldState, bot_id, message, step))
                    .then(waitBotMessageAnimation)
                    .then(addBotMessageToHistory(oldState, is_last_message_in_step));
            }, promise);
        } else {
            showButtons(oldState);
        }
        return oldState;
    };

    /**
     * render: renders the current state of the app
     */
    var render = function(state) {
        var context = {
            messages: state.messages,
            current_step: state.current_step,
            bot_spinner: state.bot_spinner,
            new_bot_message: state.new_bot_message,
            new_user_message: state.new_user_message,
            show_buttons: state.show_buttons,
            show_buttons_entering: state.show_buttons_entering,
            show_buttons_leaving: state.show_buttons_leaving,
            image_overlay: state.image_overlay,
            image_dimensions: state.image_dimensions,
            subject: state.subject
        };
        return renderView(context);
    };

    var state = init();

}
