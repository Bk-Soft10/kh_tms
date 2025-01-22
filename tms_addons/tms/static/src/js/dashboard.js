odoo.define('tms.tms_dashboard', function (require) {
'use strict';

var core = require('web.core');
var Widget = require('web.Widget');
var ControlPanelMixin = require('web.ControlPanelMixin');
var Dialog = require('web.Dialog');
var framework = require('web.framework');
var crash_manager = require('web.crash_manager');
var ActionManager = require('web.ActionManager');
var session = require('web.session');
var AbstractAction = require('web.AbstractAction');

var QWeb = core.qweb;
var _t = core._t;
var current = false;

function findA(e){
    try{
        if(e.tagName == 'A' )
            return e;
        if(e.parentNode && e.parentNode != e)
            return findA(e.parentNode);
    } catch(ex){}
    return false;
}


var tmsDashboard = AbstractAction.extend(ControlPanelMixin, {

    events: {
        //'click [action]': 'trigger_action',
        'click #tms_dashboard *': 'test_action',
        'keydown #sash-search-box': 'do_search'
    },
    test_action: function(e) {
        var a = findA(e.target);
        if(a){
            e.target = a;
            this.trigger_action(e);
        }
    },

    init: function(parent, action) {
        this.actionManager = parent;
        this.odoo_context = action.context;
        return this._super.apply(this, arguments);
    },
    start: function() {
        var self = this;
        //framework.blockUI();
        //$(".o_control_panel").addClass('hidden');
        var extra_info = this._rpc({
                model: 'tms.dashboard',
                method: 'get_html_dashboard',
                args: [1,2],
                context: self.odoo_context,
            })
            .then(function(result){
                return self.parse_reports_informations(result);
            });
        return $.when(extra_info, this._super.apply(this, arguments)).then(function() {
            self.render();
        });
    },
    parse_reports_informations: function(values) {
        this.odoo_context = values.context;
        this.main_html = values.html;
    },
    // We need this method to rerender the control panel when going back in the breadcrumb
    do_show: function() {
        this._super.apply(this, arguments);
        this.update_cp();
    },
    // Updates the control panel and render the elements that have yet to be rendered
    update_cp: function() {
        if (!this.$buttons) {
            //this.renderButtons();
        }
        var status = {
            breadcrumbs: [],
            cp_content: {},
        };
        
        var ret = this.update_control_panel(status, {clear: true});
        current = true;
        /*
        $(".o_control_panel").addClass('hidden');
        setTimeout(function(){
            if($('#tms_dashboard').length > 0)
                $(".o_control_panel").addClass('hidden');
        }, 400);*/
        //console.log("build dashboard");
        return ret;
        //$("body > .o_control_panel").html('');
        
    },
    destroy: function() {
        current = false;
        /*
        $(".o_control_panel").removeClass('hidden');
        setTimeout(function(){
            if($('#tms_dashboard').length == 0)
                $(".o_control_panel").removeClass('hidden');
        }, 200);
        */
        //console.log("destroy dashboard");
        this._super.apply(this, arguments);
    }, 
    reload: function() {
        var self = this;
        return this._rpc({
                model: 'tms.dashboard',
                method: 'get_html_dashboard',
                args: [1,2],
                context: self.odoo_context,
            })
            .then(function(result){
                self.parse_reports_informations(result);
                return self.render();
            });
    },
    render: function() {
        this.render_template();
        this.update_cp();
        //this.update_cp();
    },
    render_template: function() {
        var self = this;
        this.$el.html(this.main_html);
        
    },
    renderButtons: function() {
        var self = this;
        this.$buttons = $(QWeb.render("accountReports.buttons", {buttons: this.buttons}));
        // bind actions
        _.each(this.$buttons.siblings('button'), function(el) {
            $(el).click(function() {
                return self._rpc({
                        model: self.report_model,
                        method: $(el).attr('action'),
                        args: [self.financial_id, self.report_options],
                        context: self.odoo_context,
                    })
                    .then(function(result){
                        return self.do_action(result);
                    });
            });
        });
        return this.$buttons;
    },
    trigger_action: function(e) {
        e.preventDefault();
        e.stopPropagation();
        var self = this, t = $(e.target);
        
        var action = t.attr('action');
        var state = t.attr('state');
        var to = !! t.attr('to');
        var ctx = _.extend({'state': state, 'to': to}, self.odoo_context);
        
        if (action) {
            //framework.blockUI();
            //console.log("action to model:", this.report_model, ", ctx:"+ ctx);
            return this._rpc({
                    model: 'tms.dashboard',
                    method: action,
                    args: [state, to],
                    context: ctx,
                })
                .then(function(result){
                    //framework.unblockUI();
                    return self.do_action(result);
                });
        } else if(t.attr('id') == "show-poup"){
            $(t).popover({
                title: t.attr('title'),
                html: true,
                content: $("#popover-progress").html(),
                placement: 'auto',
                container: $(".o_content")
            });
        }
        return false;
    },
    no_trigger: function(e) {e.stopPropagation();},
    do_search: function(e) {
        if (e.keyCode != 13)
            return;
        var self = this;
        var val = e.target.value;
        if (!val)
            return false;
        var action = 'do_search';
        var ctx = _.extend({'search': val, 'to': ''}, self.odoo_context);
        if (action) {
            //console.log("action to model:", this.report_model, ", ctx:"+ ctx);
            return this._rpc({
                    model: 'tms.dashboard',
                    method: action,
                    args: [val, ''],
                    context: ctx,
                })
                .then(function(result){
                    //framework.unblockUI();
                    return self.do_action(result);
                });
        }
        return false;
    }
});

//For feature implementation
ActionManager.include({
    ir_actions_tms_dashboard: function(action, options) {
        var self = this;
        var c = crash_manager;
        return $.Deferred(function (d) {
            self.getSession().get_file({
                url: '/account_reports',
                data: action.data,
                complete: framework.unblockUI,
                success: function(){
                    if (!self.dialog) {
                        options.on_close();
                    }
                    self.dialog_stop();
                    d.resolve();
                },
                error: function () {
                    c.rpc_error.apply(c, arguments);
                    d.reject();
                }
            });
        });
    }
});
registry.category('actions').add('tms_dashboard', tmsDashboard);

return tmsDashboard;
});
 