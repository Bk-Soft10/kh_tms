/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { getDefaultConfig } from "@web/views/view";
import { useSetupAction } from "@web/webclient/actions/action_hook";
import { useEnrichWithActionLinks } from "@web/webclient/actions/reports/report_hook";

import { Component, useRef, useSubEnv } from "@odoo/owl";
import { whenReady, mount } from "@odoo/owl";

class tms_dashboard extends Component {
    static template = "tms.tms_dashboard";
   setup() {
        console.log("setup");
        useSubEnv({
            config: {
                ...getDefaultConfig(),
                ...this.env.config,
            },
        });
        useSetupAction();
        console.log("setup action");
        this.action = useService("action");
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.title = this.props.display_name || this.props.name;
        this.reportUrl = this.props.report_url;
        this.iframe = useRef("iframe");
        this.test_hno();
        //useEnrichWithActionLinks(this.iframe);
        console.log("setup end");
    }
    start() {
        var self = this;
        //framework.blockUI();
        //$(".o_control_panel").addClass('hidden');
        console.log("gggggggg");
        var extra_info = this.rpc({
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
    }
    test_hno() {
        var self = this;
        //framework.blockUI();
        //$(".o_control_panel").addClass('hidden');
        console.log("gggggggg");
        this.orm.call("tms.dashboard", "get_html_dashboard", [1,2], {}).then(function(result){
            console.log(result);
            self.parse_reports_informations(result);
            self.render();
        });
//        var extra_info = this.rpc({
//                model: 'tms.dashboard',
//                method: 'get_html_dashboard',
//                args: [1,2],
//                context: self.odoo_context,
//            })
//            .then(function(result){
//                console.log(result);
//                return self.parse_reports_informations(result);
//            });
//        console.log(result);
//        self.render();
    }
    parse_reports_informations(values) {
        this.odoo_context = values.context;
        this.main_html = values.html;
    }

    onIframeLoaded(ev) {
        console.log("iframeee");
        const iframeDocument = ev.target.contentWindow.document;
        iframeDocument.body.classList.add("o_in_iframe", "container-fluid");
        iframeDocument.body.classList.remove("container");
    }
      trigger_action () {
        e.preventDefault();
        e.stopPropagation();
        var self = this, t = $(e.target);

        console.log("trigger_action");
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
    }
    no_trigger () {e.stopPropagation();}
    do_search () {
        console.log("do_search");
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
}
//whenReady().then(() => {
//    mount(tms_dashboard, document.getElementById("tms_dashboard"));
//});
tms_dashboard.components = { Layout };
registry.category("actions").add("tms_dashboard", tms_dashboard);