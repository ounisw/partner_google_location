import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { CharField, charField } from "@web/views/fields/char/char_field";

/** WhatsApp message: company / person name, phone (if any), address, Google Maps link. */
export function shareText(name, phone, addressParts, mapsUrl) {
    const address = (addressParts || []).filter(Boolean).join(", ");
    return [name, phone ? `📞 ${phone}` : "", address, mapsUrl].filter(Boolean).join("\n");
}

/**
 * Char field holding a Google Maps link, with the map of the location below it,
 * a link to open Google Maps, and a "My current position" button (browser GPS).
 * The coordinates are read from the link on the server (partner_latitude / longitude).
 */
export class GoogleLocationField extends CharField {
    static template = "partner_google_location.GoogleLocationField";

    setup() {
        super.setup();
        this.notification = useService("notification");
    }

    get coordinates() {
        const lat = this.props.record.data.partner_latitude;
        const lng = this.props.record.data.partner_longitude;
        return lat || lng ? `${lat},${lng}` : "";
    }

    get embedUrl() {
        const c = this.coordinates;
        return c ? `https://maps.google.com/maps?q=${c}&z=16&hl=${this.lang}&output=embed` : "";
    }

    get mapsUrl() {
        const c = this.coordinates;
        if (c) {
            return `https://www.google.com/maps/search/?api=1&query=${c}`;
        }
        return this.props.record.data[this.props.name] || "";
    }

    /** WhatsApp share link: name, address and the Google Maps link (the user picks the recipient). */
    get whatsappUrl() {
        const c = this.coordinates;
        if (!c) {
            return "";
        }
        const data = this.props.record.data;
        const text = shareText(data.display_name || data.name, data.phone, [data.street, data.city], this.mapsUrl);
        return `https://wa.me/?text=${encodeURIComponent(text)}`;
    }

    get lang() {
        return (document.documentElement.lang || "en").slice(0, 2);
    }

    useMyPosition() {
        if (!navigator.geolocation) {
            this.notification.add(_t("This browser cannot give your position."), { type: "warning" });
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude.toFixed(7);
                const lng = position.coords.longitude.toFixed(7);
                this.props.record.update({
                    [this.props.name]: `https://www.google.com/maps?q=${lat},${lng}`,
                    partner_latitude: Number(lat),
                    partner_longitude: Number(lng),
                });
            },
            () => {
                this.notification.add(
                    _t("Position not available: allow the location access in the browser."),
                    { type: "warning" }
                );
            },
            { enableHighAccuracy: true, timeout: 15000 }
        );
    }
}

export const googleLocationField = {
    ...charField,
    component: GoogleLocationField,
    displayName: _t("Google Maps location"),
    supportedTypes: ["char"],
    fieldDependencies: [
        { name: "partner_latitude", type: "float" },
        { name: "partner_longitude", type: "float" },
        { name: "display_name", type: "char" },
        { name: "phone", type: "char" },
        { name: "street", type: "char" },
        { name: "city", type: "char" },
    ],
};

registry.category("fields").add("google_location", googleLocationField);

/**
 * Large Google map of the partner location, shown at the bottom of the contact form.
 */
export class GoogleLocationMapField extends GoogleLocationField {
    static template = "partner_google_location.GoogleLocationMapField";
}

export const googleLocationMapField = {
    ...googleLocationField,
    component: GoogleLocationMapField,
    displayName: _t("Google map"),
};

registry.category("fields").add("google_location_map", googleLocationMapField);

/**
 * List column: a map pin opening the location in Google Maps (no map, no editing).
 */
export class GoogleLocationLinkField extends GoogleLocationField {
    static template = "partner_google_location.GoogleLocationLinkField";
}

export const googleLocationLinkField = {
    ...googleLocationField,
    component: GoogleLocationLinkField,
    displayName: _t("Google Maps link"),
};

registry.category("fields").add("google_location_link", googleLocationLinkField);
