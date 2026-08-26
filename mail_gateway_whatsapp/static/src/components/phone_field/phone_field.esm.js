import {
    PhoneField,
    phoneField,
    formPhoneField,
} from "@web/views/fields/phone/phone_field";
import {SendWhatsappButton} from "../send_whatsapp_button/send_whatsapp_button.esm";
import {patch} from "@web/core/utils/patch";

patch(PhoneField, {
    components: {
        ...PhoneField.components,
        SendWhatsappButton,
    },
    defaultProps: {
        ...PhoneField.defaultProps,
        enableButton: true,
    },
    props: {
        ...PhoneField.props,
        enableButton: {type: Boolean, optional: true},
    },
});

function extendExtractProps(descriptor) {
    const originalExtractProps = descriptor.extractProps;
    return (fieldInfo, dynamicInfo) => ({
        ...originalExtractProps(fieldInfo, dynamicInfo),
        enableButton: fieldInfo.options.enable_sms,
    });
}

// `extractProps` lives on the field registry descriptor, not on the
// component class, so it has to be patched on `phoneField`/`formPhoneField`
// (the objects registered via `registry.category("fields")`) rather than
// on `PhoneField` itself.
patch(phoneField, {extractProps: extendExtractProps(phoneField)});
patch(formPhoneField, {extractProps: extendExtractProps(formPhoneField)});
