import { registry } from '@web/core/registry';
import { patch } from '@web/core/utils/patch';

import { ChatHub } from '@mail/core/common/chat_hub_model';
import { ChatDock, dockWidth } from '@muk_ai/chat/dock/dock';
import { ChatWindow } from '@muk_ai/chat/window/window';

const CODE_WINDOW_EXTRA_WIDTH = 57;
const DOCK_RIGHT = 16;

function codeWindowExtraWidth(chat) {
    return chat.windows.filter((entry) => entry.blueCodeWindow).length
        * CODE_WINDOW_EXTRA_WIDTH;
}

/** Reuse the native window and keep enlargement within the current business page. */
class BlueCodeChatWindow extends ChatWindow {
    static template = 'blue_ai_client.CodeChatWindow';

    codeWindow() {
        return this.chat.windows.find(
            (entry) => entry.id === this.props.id && entry.blueCodeWindow,
        );
    }

    toggleCodeWindowSize() {
        const entry = this.codeWindow();
        entry.blueExpanded = !entry.blueExpanded;
    }
}

class BlueCodeChatDock extends ChatDock {
    static components = { ...ChatDock.components, ChatWindow: BlueCodeChatWindow };

    get width() {
        return super.width + codeWindowExtraWidth(this.chat);
    }
}

registry.category('main_components').add(
    'muk_ai.ChatDock', { Component: BlueCodeChatDock }, { force: true },
);

registry.category('actions').add('blue_ai_client.open_code_chat', (env, action) => {
    const chat = env.services['muk_ai.chat'];
    const id = Number(action.params.session_id);
    chat.openWindow(id);
    const entry = chat.windows.find((window) => window.id === id);
    entry.blueCodeWindow = true;
    entry.blueExpanded = false;
    // Function actions leave the form controller and URL in place.
});

// MuK reserves fixed 380px slots in Discuss separately from its dock renderer.
// Account only for the extra width of code windows; ordinary AI windows keep
// their existing size and fullscreen behavior.
patch(ChatHub.prototype, {
    get maxOpened() {
        const chat = this.store.env.services['muk_ai.chat'];
        const extra = codeWindowExtraWidth(chat);
        const original = super.maxOpened;
        if (!extra) {
            return original;
        }
        const width = dockWidth(chat.windows.length);
        const slot = this.WINDOW + this.WINDOW_INBETWEEN;
        const oldSlots = Math.ceil((DOCK_RIGHT + width) / slot);
        const newSlots = Math.ceil((DOCK_RIGHT + width + extra) / slot);
        return Math.max(1, original - (newSlots - oldSlots));
    },
});
