odoo.define('tms.tms_commission', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var ControlPanelMixin = require('web.ControlPanelMixin');
var Dialog = require('web.Dialog');
var framework = require('web.framework');
var crash_manager = require('web.crash_manager');
var ActionManager = require('web.ActionManager');
var session = require('web.session');

var QWeb = core.qweb;
var _t = core._t;

var CommissionDialog = Dialog.extend({
    template: "PlannerDialog",
    category_selector: "div[menu-category-id]",
    events: {
        "click li a[href^=\"#\"]:not([data-toggle=\"collapse\"])": function (e) {
            e.preventDefault();
            this._display_page($(e.currentTarget).attr("href").replace("#", ""));
        },
    },
    init: function (parent, options) {
        this._super.apply(this, arguments);

        this.planner = planner;
        this.cookie_name = this.planner.planner_application + '_last_page';
        this.pages = [];
        this.menu_items = [];
        this.currently_shown_page = null;
        this.currently_active_menu_item = null,

        this.on("change:progress", this, function () {
            this.trigger('planner_progress_changed', this.get('progress'));
        });
        this.set("progress", this.planner.progress || MIN_PROGRESS);
    },
    /**
     * Fetch the planner's rendered template
     */
    willStart: function() {
        var def = rpc.query({
                model: 'tms.commission',
                method: 'render',
                args: [this.planner.view_id[0], this.planner.planner_application],
                context: session.user_context,
            })
            .then((function (template) {
                this.$template = $(template);
            }).bind(this));

        return $.when(this._super.apply(this, arguments), def);
    },
    start: function() {
        this.$modal.addClass("o_planner_dialog");
        return this._super.apply(this, arguments);
    },
});

})