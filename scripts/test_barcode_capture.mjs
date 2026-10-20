import assert from 'node:assert/strict';
import test from 'node:test';
import { readFile } from 'node:fs/promises';
const source = await readFile(new URL('../blue_barcode_base/static/src/scanning/pda_capture.js', import.meta.url), 'utf8');
const { PdaCapture } = await import(`data:text/javascript,${encodeURIComponent(source)}`);

function fixture(input = null) {
    let callback;
    const scans = [];
    const control = { active: true };
    const capture = new PdaCapture({
        emit: (raw) => scans.push(raw), input,
        isActive: () => control.active,
        timers: {setTimeout(fn) { callback = fn; return 1; }, clearTimeout() { callback = null; }},
    });
    const event = (key, target = {closest: () => null}, more = {}) => ({
        key, target, ...more, preventDefault() { this.prevented = true; },
        stopPropagation() { this.stopped = true; },
    });
    const type = (raw) => { for (const key of raw) capture.keydown(event(key)); };
    return {capture, scans, control, event, type, idle: () => callback?.()};
}

test('one full QR event preserves semicolon, pipe, empty fields and literal modifier words', () => {
    const f = fixture();
    const raw = 'HDR##Control;Shift|SKU#12#';
    f.type(raw);
    f.capture.keydown(f.event('Enter'));
    assert.deepEqual(f.scans, [raw]);
});

test('a scanner without a terminator emits after the idle boundary', () => {
    const f = fixture();
    f.type('000123'); f.idle();
    assert.deepEqual(f.scans, ['000123']);
});

test('CR/LF terminators cannot emit a second count', () => {
    const f = fixture();
    f.type('SKU1'); f.capture.keydown(f.event('Enter')); f.capture.keydown(f.event('Enter')); f.idle();
    assert.deepEqual(f.scans, ['SKU1']);
});

test('two physical scans of the same code are two separate events', () => {
    const f = fixture();
    for (let n = 0; n < 2; n++) { f.type('SKU1'); f.capture.keydown(f.event('Tab')); }
    assert.deepEqual(f.scans, ['SKU1', 'SKU1']);
});

test('PDA text injection into the native hidden input emits once and preserves embedded delimiters', () => {
    const input = {value: '', closest: () => ({})};
    const f = fixture(input);
    f.capture.keydown(f.event('S', input));
    input.value = 'HDR#SKU;1\nINNER\r\n';
    f.capture.inputEvent(f.event('', input));
    f.capture.keydown(f.event('Enter', input));
    assert.deepEqual(f.scans, ['HDR#SKU;1\nINNER']);
});

test('Ctrl+] preserves the GS1 group separator', () => {
    const f = fixture();
    f.type('10LOT'); f.capture.keydown(f.event(']', undefined, {ctrlKey: true})); f.type('3012'); f.idle();
    assert.deepEqual(f.scans, ['10LOT\x1d3012']);
});

test('search and quantity editing keep their ordinary keyboard input', () => {
    const f = fixture();
    const event = f.event('1', {closest: () => ({})});
    f.capture.keydown(event); f.idle();
    assert.equal(event.prevented, undefined);
    assert.deepEqual(f.scans, []);
});

test('inactive pages and quantity dialogs do not consume barcode events', () => {
    const f = fixture();
    f.type('OLD'); f.control.active = false; f.capture.keydown(f.event('Enter'));
    f.control.active = true; f.type('NEW'); f.idle();
    assert.deepEqual(f.scans, ['NEW']);
});

test('page unmount removes capture listeners and drops incomplete input', () => {
    const f = fixture(); const listeners = new Map();
    const target = {addEventListener(key, fn) { listeners.set(key,fn); }, removeEventListener(key) { listeners.delete(key); }};
    f.capture.attach(target); f.type('PARTIAL'); f.capture.destroy(); f.idle();
    assert.equal(listeners.size, 0);
    assert.deepEqual(f.scans, []);
});
