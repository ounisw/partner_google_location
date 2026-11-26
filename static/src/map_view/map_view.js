import { Component, onMounted, onWillStart, onWillUnmount, onWillUpdateProps, useRef, useState } from "@odoo/owl";
import { loadCSS, loadJS } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { Layout } from "@web/search/layout";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { useSearchBarToggler } from "@web/search/search_bar/search_bar_toggler";
import { standardViewProps } from "@web/views/standard_view_props";
import { shareText } from "../google_location_field";

const LIB = "/partner_google_location/static/lib/leaflet";
const LOCATED = ["|", ["partner_latitude", "!=", 0], ["partner_longitude", "!=", 0]];
const FIELDS = ["display_name", "phone", "street", "city", "partner_latitude", "partner_longitude"];
const BASE_LAYER_KEY = "partner_google_location.map_base_layer";
const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";

function readBaseLayer() {
    try {
        return localStorage.getItem(BASE_LAYER_KEY) === "satellite" ? "satellite" : "plan";
    } catch {
        return "plan";
    }
}

/**
 * "map" view of contacts: the standard Odoo search bar (filters, favorites) and a pin
 * for each contact of the search that has coordinates (OpenStreetMap tiles, no API key).
 */
export class MapController extends Component {
    static template = "partner_google_location.MapView";
    static components = { Layout, CogMenu, SearchBar };
    static props = { ...standardViewProps };

    setup() {
        this.orm = useService("orm");
        this.mapRef = useRef("map");
        this.searchBarToggler = useSearchBarToggler();
        this.state = useState({ located: 0, total: 0, baseLayer: readBaseLayer() });
        this.records = [];
        onWillStart(async () => {
            await loadCSS(`${LIB}/leaflet.css`);
            await loadJS(`${LIB}/leaflet.js`);
            await this.load(this.props);
        });
        onWillUpdateProps(async (nextProps) => {
            if (JSON.stringify(nextProps.domain) !== JSON.stringify(this.props.domain)) {
                await this.load(nextProps);
                this.drawMarkers();
            }
        });
        onMounted(() => this.initMap());
        onWillUnmount(() => this.map && this.map.remove());
    }

    async load(props) {
        const context = props.context;
        const [records, total] = await Promise.all([
            this.orm.searchRead(props.resModel, [...props.domain, ...LOCATED], FIELDS, {
                order: "name, id",
                context,
            }),
            this.orm.searchCount(props.resModel, props.domain, { context }),
        ]);
        this.records = records;
        this.state.located = records.length;
        this.state.total = total;
    }

    initMap() {
        const L = window.L;
        L.Icon.Default.imagePath = `${LIB}/images/`;
        this.map = L.map(this.mapRef.el).setView([21.5433, 39.1728], 11);
        this.baseLayers = {
            plan: L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
            }),
            // Esri World Imagery + place names on top (free, attribution required)
            satellite: L.layerGroup([
                L.tileLayer(`${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`, {
                    maxZoom: 19,
                    maxNativeZoom: 18,
                    attribution: "Tiles &copy; Esri &mdash; Source: Esri, Maxar, Earthstar Geographics, and the GIS User Community",
                }),
                L.tileLayer(`${ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}`, {
                    maxZoom: 19,
                    maxNativeZoom: 18,
                }),
            ]),
        };
        this.baseLayers[this.state.baseLayer].addTo(this.map);
        this.layer = L.featureGroup().addTo(this.map);
        this.drawMarkers();
        // the container gets its final size once the action is displayed
        setTimeout(() => this.map && this.map.invalidateSize(), 200);
    }

    drawMarkers() {
        const L = window.L;
        this.layer.clearLayers();
        for (const record of this.records) {
            L.marker([record.partner_latitude, record.partner_longitude], { title: record.display_name })
                .bindPopup(() => this.popup(record))
                .addTo(this.layer);
        }
        if (this.records.length) {
            this.map.fitBounds(this.layer.getBounds(), { padding: [40, 40], maxZoom: 15 });
        }
    }

    setBaseLayer(name) {
        if (name === this.state.baseLayer) {
            return;
        }
        this.map.removeLayer(this.baseLayers[this.state.baseLayer]);
        this.baseLayers[name].addTo(this.map);
        this.state.baseLayer = name;
        try {
            localStorage.setItem(BASE_LAYER_KEY, name);
        } catch {
            // private browsing: the choice is simply not remembered
        }
    }

    popup(record) {
        // DOM nodes with textContent: names and addresses are never read as HTML
        const el = document.createElement("div");
        const add = (parent, tag, text, cls) => {
            const node = document.createElement(tag);
            node.textContent = text;
            if (cls) {
                node.className = cls;
            }
            parent.appendChild(node);
            return node;
        };
        add(el, "strong", record.display_name, "d-block mb-1");
        const address = [record.street, record.city].filter(Boolean).join(", ");
        if (address) {
            add(el, "div", address);
        }
        if (record.phone) {
            add(el, "a", record.phone, "d-block").href = `tel:${record.phone.replace(/\s/g, "")}`;
        }
        const actions = add(el, "div", "", "d-flex gap-3 mt-2");
        const open = add(actions, "a", _t("Open"));
        open.href = "#";
        open.onclick = (ev) => {
            ev.preventDefault();
            this.props.selectRecord(record.id, { activeIds: this.records.map((r) => r.id) });
        };
        const gmaps = add(actions, "a", "Google Maps");
        gmaps.href = `https://www.google.com/maps/search/?api=1&query=${record.partner_latitude},${record.partner_longitude}`;
        gmaps.target = "_blank";
        gmaps.rel = "noopener noreferrer";
        const text = shareText(record.display_name, record.phone, [record.street, record.city], gmaps.href);
        const whatsapp = add(actions, "a", "WhatsApp", "text-success");
        whatsapp.href = `https://wa.me/?text=${encodeURIComponent(text)}`;
        whatsapp.target = "_blank";
        whatsapp.rel = "noopener noreferrer";
        whatsapp.title = _t("Share via WhatsApp");
        return el;
    }
}

export const mapView = {
    type: "map",
    display_name: _t("Map"),
    icon: "fa fa-map-marker",
    multiRecord: true,
    Controller: MapController,
    searchMenuTypes: ["filter", "favorite"],
};

registry.category("views").add("map", mapView);
