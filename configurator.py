# coding: utf8
import os, subprocess, datetime, fileinput
from flask import Flask, flash, request, redirect, url_for, send_from_directory, jsonify

ALLOWED_EXTENSIONS = set(['json'])


app = Flask(__name__)

# Returns the file to download at the very end
@app.route('/downloads/<filename>')
def download_file(filename):
    return send_from_directory("/app/qmk_firmware", filename, as_attachment=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/import/', methods=['PUT'])
def import_layout():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']

    return file.read()

# This is our main routine. it allows GET and POST requests. If we get a GET request, we just send our template file
# to the browser (at the very end of the function) If it's a POST request, it means the browser already has our
# template and wants to send the values back to us. We do some sanity checks first to see if everything is ok The
# other steps we take will be explained right before everything.
@app.route('/', methods=['GET', 'POST'])
def main():
    if request.method == 'POST':
        keyboard = request.get_json()

        firmware_directory = setupFirmware(
                keyboard.get('config'),
                keyboard.get('rules'),
                keyboard.get('configKeymap'),
                keyboard.get('keymap'),
                keyboard.get('indicators'))

        buildFirmware(firmware_directory)

        #return redirect(url_for('download_file', filename='{}_default.hex'.format(firmware_directory)))
        return jsonify({'hex_url': '/downloads/{}_default.hex'.format(firmware_directory)})

    #this is what happens on a GET request, we just send the index.htm file.
    else:
        return send_from_directory("/app/frontend/", "index.html")

def buildFirmware(firmware_directory):
    callstring = 'make {}'.format(firmware_directory)
    subprocess.call(callstring, shell=True, cwd="/app/qmk_firmware/")

def setupFirmware(config, rules, configKeymap, keymap, indicators):
    now = str(datetime.datetime.now()).replace('-', '').replace(' ', '').replace(':', '').split(".")[0]

    firmware_directory = '{}{}'.format(config.get('product').replace(' ', ''), now)
    os.makedirs('/app/qmk_firmware/keyboards/{}/keymaps/default'.format(firmware_directory), exist_ok=True)

    with open("/app/qmk_firmware/keyboards/{}/{}".format(firmware_directory, 'config.h'), "w+") as configfile:
        configfile.write(buildConfig(config))
        configfile.close()

    with open("/app/qmk_firmware/keyboards/{}/{}".format(firmware_directory, 'makefile'), "w+") as makefile:
        makefile.write('ifndef MAKEFILE_INCLUDED\ninclude ../../Makefile\nendif')
        makefile.close()

    with open("/app/qmk_firmware/keyboards/{}/{}".format(firmware_directory, 'rules.mk'), "w+") as rulesfile:
        rulesfile.write(buildRules(rules))
        rulesfile.close()

    with open("/app/qmk_firmware/keyboards/{}/{}".format(firmware_directory, '{}.c'.format(firmware_directory)), "w+") as keyboardcfile:
        keyboardcfile.write(buildProductC(firmware_directory, indicators))
        keyboardcfile.close()

    with open("/app/qmk_firmware/keyboards/{}/{}".format(firmware_directory, '{}.h'.format(firmware_directory)), "w+") as keyboardhfile:
        keyboardhfile.write(buildKeyboardHeader(configKeymap, firmware_directory))
        keyboardhfile.close()

    with open("/app/qmk_firmware/keyboards/{}/keymaps/default/keymap.c".format(firmware_directory), "w+") as keymapfile:
        keymapfile.write(buildKeymap(keymap, indicators, firmware_directory))
        keymapfile.close()

    return firmware_directory

def buildProductC(firmware_directory, hasIndicators):
    template =  '#include "{}.h"\n'.format(firmware_directory)
    template += 'void matrix_init_kb(void) {\n'
    template += 'matrix_init_user();\n'
    template += '}\n'
    template += 'void matrix_scan_kb(void) {\n'
    template += '  	matrix_scan_user();\n'
    template += '}\n'

    template += 'bool process_record_kb(uint16_t keycode, keyrecord_t *record) {\n'
    template += '	return process_record_user(keycode, record);\n'
    template += '}\n'

    template += 'void led_set_kb(uint8_t usb_led) {\n'
    template += '	led_set_user(usb_led);\n'
    template += '}'

    return template


def buildConfig(config):
    template =  '#ifndef CONFIG_H\n'
    template += '#define CONFIG_H\n'
    template += '#include "config_common.h"\n'

    template += '#define VENDOR_ID       {}\n'.format(config.get('vendorId'))
    template += '#define PRODUCT_ID      {}\n'.format(config.get('productId'))
    template += '#define DEVICE_VER      {}\n'.format(config.get('deviceVersion'))
    template += '#define MANUFACTURER    {}\n'.format(config.get('manufacturer'))
    template += '#define PRODUCT         {}\n'.format(config.get('product'))
    template += '#define DESCRIPTION     {}\n'.format(config.get('description'))

    template += '#define MATRIX_ROWS {}\n'.format(len(config.get('matrixRowPins')))
    template += '#define MATRIX_COLS {}\n'.format(len(config.get('matrixColumnPins')))

    template += '#define MATRIX_ROW_PINS {{ {} }}\n'.format(', '.join(config.get('matrixRowPins')))
    template += '#define MATRIX_COL_PINS {{ {} }}\n'.format(', '.join(config.get('matrixColumnPins')))
    template += '#define UNUSED_PINS\n'

    template += '#define DIODE_DIRECTION {}\n'.format(config.get('diodeDirection'))

    if config.get('matrixHasGhost'):
        template += '#define MATRIX_HAS_GHOST\n'

    template += '#define BACKLIGHT_LEVELS  {}\n'.format(config.get('backlightLevels'))
    template += '#define BACKLIGHT_PIN {}\n'.format(config.get('backlightPin'))

    if config.get('usbMaxPowerConsumption'):
        template += '#define USB_MAX_POWER_CONSUMPTION {}\n'.format(config.get('usbMaxPowerConsumption'))

    template += '#define DEBOUNCING_DELAY  {}\n'.format(config.get('debouncingDelay'))
    template += '#define TAPPING_TERM      {}\n'.format(config.get('tappingTerm'))

    if config.get('lockingSupportEnabled'):
        template += '#define LOCKING_SUPPORT_ENABLE\n'
    if config.get('lockingResyncEnabled'):
        template += '#define LOCKING_RESYNC_ENABLE\n'

    template += '#define IS_COMMAND() ( \\\n'
    template += '    {} \\\n'.format(config.get('commandKeyCombination'))
    template += ')\n'

    if not config.get('debugEnabled'):
        template += '#define NO_DEBUG\n'

    if not config.get('printEnabled'):
        template += '#define NO_PRINT\n'

    if not config.get('actionLayerEnabled'):
        template += '#define NO_ACTION_LAYER\n'

    if not config.get('actionTappingEnabled'):
        template += '#define NO_ACTION_TAPPING\n'

    if not config.get('actionOneShotEnabled'):
        template += '#define NO_ACTION_ONESHOT\n'

    if not config.get('actionMacroEnabled'):
        template += '#define NO_ACTION_MACRO\n'

    if not config.get('actionFunctionEnabled'):
        template += '#define NO_ACTION_FUNCTION\n'

    if config.get('rgbDiPin'):
        template += '#define RGB_DI_PIN {}\n'.format(config.get('rgbDiPin'))

    if config.get('rgbLedNum'):
        template += '#define RGBLED_NUM {}\n'.format(config.get('rgbLedNum'))
        template += '#define RGBLIGHT_CUSTOM_LED_INIT\n'
        template += '#define RGBLIGHT_SLEEP\n'

    template += '#endif'

    return template;

def buildRules(rules):
    template =  'MCU = {}\n'.format(rules.get('mcu'))
    template += 'F_CPU = {}\n'.format(rules.get('processorFrequency'))
    template += 'ARCH = {}\n'.format(rules.get('architecture'))
    template += 'F_USB = {}\n'.format(rules.get('inputClockFrequency'))

    template += 'OPT_DEFS += -DINTERRUPT_CONTROL_ENDPOINT\n'
    template += 'OPT_DEFS += -DBOOTLOADER_SIZE={}\n'.format(rules.get('bootloaderSize'))

    if rules.get('bootmagicEnabled'):
        template += 'BOOTMAGIC_ENABLE = yes\n'

    if rules.get('mousekeyEnabled'):
        template += 'MOUSEKEY_ENABLE = yes\n'

    if rules.get('extrakeyEnabled'):
        template += 'EXTRAKEY_ENABLE = yes\n'

    if rules.get('consoleEnabled'):
        template += 'CONSOLE_ENABLE = yes\n'

    if rules.get('commandEnabled'):
        template += 'COMMAND_ENABLE = yes\n'

    if rules.get('sleepLedEnabled'):
        template += 'SLEEP_LED_ENABLE = yes\n'

    if rules.get('nkroEnabled'):
        template += 'NKRO_ENABLE = yes\n'

    if rules.get('backlightEnabled'):
        template += 'BACKLIGHT_ENABLE = yes\n'

    if rules.get('rgbLightEnabled'):
        template += 'RGBLIGHT_ENABLE = yes\n'

    return template


def buildKeyboardHeader(configKeymap, firmware_directory):
    keys = ', '.join(configKeymap.get('keys'))

    template =  '#ifndef {}_H\n'.format(firmware_directory.upper())
    template += '#define {}_H\n'.format(firmware_directory.upper())
    template += '#include "quantum.h"\n'

    template += '#define KEYMAP({}) {{ \\\n'.format(keys)

    for row in configKeymap.get('positions'):
        template += '{{ {} }}, \\\n'.format(', '.join(row))

    template += '}\n#endif\n'
    template += 'void process_indicator_update(void);'

    return template

def prepKeyForTemplate(key):

    key_type = key.get('type')
    key_value = key.get('value')
    key_secondary = key.get('secondary')

    LAYER_TYPE_MAP = {
        'momentary': 'MO',
        'toggle': 'TG',
        'direct': 'TO',
        'taptoggle': 'TT',
        'setdefaultlayer': 'DF'
    }

    EXEMPT_CODES = {
        'RESET': True,
        'BL_TOGG': True,
        'BL_STEP': True,
        'BL_INC': True,
        'BL_DEC': True,
        'RGB_VAI': True,
        'RGB_VAD': True
    }

    if key_type == 'normal':
        if key_value in EXEMPT_CODES:
            return key_value
        
        if key_value == 'IME':
            return 'M_IME'

        return 'KC_{}'.format(key_value)

    elif key_type == 'modkey' or key_type == 'combokey':
        return '{}(KC_{})'.format(key_secondary, key_value)

    elif key_type == 'tapkey':
        if key_secondary[1:].isdigit():
            return 'LT({}, KC_{})'.format(key_secondary[1:], key_value)
        return '{}_T(KC_{})'.format(key_secondary, key_value)

    elif key_type in LAYER_TYPE_MAP:
        return '{}({})'.format(LAYER_TYPE_MAP[key_type], key_value[1:])

    elif key_type == 'oneshotmod' or key_type == 'oneshotlayer':
        if key_value[1:].isdigit():
            return 'OSL({})'.format(key_value[1:])
        return 'OSM({})'.format(key_value)

    elif key_type == 'unicode':
        return 'UC({})'.format(key_value)

    else:
        return 'KC_NO'


def buildKeymap(keyData, fn_indicators, firmware_directory):
    layers = []

    for layer in keyData:
        layer_keys = []
        for row in layer:
            for key in row:
                layer_keys.append(prepKeyForTemplate(key))

        layers.append(layer_keys)

    template =  '#include "{}.h"\n'.format(firmware_directory)
    template += 'enum custom_keycodes {\n'
    template += 'M_IME = SAFE_RANGE\n'
    template += '};\n'
    template += 'bool process_record_user(uint16_t keycode, keyrecord_t *record) {\n'
    template += 'if (record->event.pressed) {\n'
    template += 'switch(keycode) {\n'
    template += 'case M_IME:\n'
    template += 'SEND_STRING(SS_DOWN(X_LSHIFT)SS_DOWN(X_LALT));\n'
    template += 'return false;\n'
    template += '}\n'
    template += '}\n'
    template += 'else if (record->event.released) {\n'
    template += 'switch(keycode) {\n'
    template += 'case M_IME:\n'
    template += 'SEND_STRING(SS_UP(X_LSHIFT)SS_UP(X_LALT));\n'
    template += 'return false;\n'
    template += '}\n'
    template += '}\n'
    template += 'return true;\n'
    template += '};\n'
    template += 'const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {\n'
    for index, layer in enumerate(layers):
        template += '[{}] = KEYMAP({}),\n'.format(index, ', '.join(layer))

    template += '};\n'

    if fn_indicators:
        #init
        template += 'void matrix_init_user(void) {\n'
        template += 'rgblight_init();\n'
        template += '};\n'
        template += 'void rgblight_init_leds(void) {\n'
        template += 'process_indicator_update();\n'
        template += '};\n'

        #keyboard indicators trigger
        template += 'void led_set_user(uint8_t usb_led) {\n'
        template += 'process_indicator_update();\n'
        template += '};\n'

        #layer indicators trigger
        template += 'uint32_t layer_state_set_kb(uint32_t state) {\n'
        template += 'process_indicator_update();\n'
        template += 'return state;\n'
        template += '};\n'

        #process indicator update
        template += 'void process_indicator_update(void) {\n'
        template += 'LED_TYPE indicators[{}] = {{\n'.format(len(fn_indicators))
        for index in range(len(fn_indicators)):
            template += '{.r = 0, .g = 0, .b = 0},\n'
        template = template[:-2]
        template += '\n};\n'

        template += 'uint8_t indexes[{}] = {{\n'.format(len(fn_indicators))
        for index in range(len(fn_indicators)):
            template += '{},\n'.format(index)
        template = template[:-2]
        template += '\n};\n'

        for index, led in enumerate(fn_indicators):
            for trigger in led:
                if trigger.get('type') == 'layer':
                    template += 'if (layer_state & (1<<{})){{\n'.format(trigger.get('action')[1:])
                    template += 'indicators[{}].r = {};\n'.format(index, trigger.get('red'))
                    template += 'indicators[{}].g = {};\n'.format(index, trigger.get('green'))
                    template += 'indicators[{}].b = {};\n'.format(index, trigger.get('blue'))
                    template += '}\n'

                elif trigger.get('type') == 'keyboard':
                    template += 'if (host_keyboard_leds() & (1<<{})){{\n'.format(trigger.get('action'))
                    template += 'if (indicators[{index}].r > 0) {{indicators[{index}].r = (indicators[{index}].r + {new}) / 2;}}\n'.format(index=index, new=trigger.get('red'))
                    template += 'else {{indicators[{}].r = {};}}\n'.format(index, trigger.get('red'))
                    template += 'if (indicators[{index}].g > 0) {{indicators[{index}].g = (indicators[{index}].g + {new}) / 2;}}\n'.format(index=index, new=trigger.get('green'))
                    template += 'else {{indicators[{}].g = {};}}\n'.format(index, trigger.get('green'))
                    template += 'if (indicators[{index}].b > 0) {{indicators[{index}].b = (indicators[{index}].b + {new}) / 2;}}\n'.format(index=index, new=trigger.get('blue'))
                    template += 'else {{indicators[{}].b = {};}}\n'.format(index, trigger.get('blue'))
                    template += '}\n'

                elif trigger.get('type') == 'power':
                    template += 'indicators[{}].r = {};\n'.format(index, trigger.get('red'))
                    template += 'indicators[{}].g = {};\n'.format(index, trigger.get('green'))
                    template += 'indicators[{}].b = {};\n'.format(index, trigger.get('blue'))

        template += 'rgblight_setrgb_many(indicators, indexes, {});\n'.format(len(fn_indicators))
        template += '};'

    return template
