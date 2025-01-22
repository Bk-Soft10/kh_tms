odoo.define('tms.report_preview', function (require) {
"use strict";

var ActionManager = require('web.ActionManager');
var core = require('web.core');
var crash_manager = require('web.crash_manager');
var framework = require('web.framework');
var session = require('web.session');

var _t = core._t;
var wkhtmltopdf_state;

var make_report_url = function (action) {
    var report_urls = {
        'qweb-html': '/report/html/' + action.report_name,
        'qweb-pdf': '/report/pdf/' + action.report_name,
        'controller': action.report_file
    };
    // We may have to build a query string with `action.data`. It's the place
    // were report's using a wizard to customize the output traditionally put
    // their options.
    if (_.isUndefined(action.data) || _.isNull(action.data) || (_.isObject(action.data) && _.isEmpty(action.data))) {
        if (action.context.active_ids) {
            var active_ids_path = '/' + action.context.active_ids.join(',');
            // Update the report's type - report's url mapping.
            report_urls = _.mapObject(report_urls, function (value, key) {
                return value += active_ids_path;
            });
        }
    } else {
        var serialized_options_path = '?options=' + encodeURIComponent(JSON.stringify(action.data));
        serialized_options_path += '&context=' + encodeURIComponent(JSON.stringify(action.context));
        // Update the report's type - report's url mapping.
        report_urls = _.mapObject(report_urls, function (value, key) {
            return value += serialized_options_path;
        });
    }
    return report_urls;
};

var trigger_download_org = function (session, response, c, action, options) {
    session.get_file({
        url: '/report/download',
        data: {data: JSON.stringify(response)},
        complete: framework.unblockUI,
        error: c.rpc_error.bind(c),
        success: function () {
            if (action && options && !action.dialog) {
                options.on_close();
            }
        },
    });
};


var trigger_download = function(session, response, c, action, options) {
    window.ssession = session;
    var params = {
        data: JSON.stringify(response),
        token: new Date().getTime()
    };
    var url = session.url('/report/download', params);
    var w = window.open(url, 'report');
    framework.unblockUI();
    w.focus();
};

ActionManager.include({
    ir_actions_report: function(action, options) {
        var self = this;
        
        framework.blockUI();
        action = _.clone(action);
        _t =  core._t;
        var c = crash_manager;
        var report_url = make_report_url(action);
        
        var response = new Array();
        
        
        // QWeb reports
        if ('report_type' in action && (action.report_type == 'qweb-html' || action.report_type == 'qweb-pdf' || action.report_type == 'controller')) {
            
            
            switch (action.report_type) {
                case 'qweb-html':
                    report_url = report_url['qweb-html'];
                    break;
                case 'qweb-pdf':
                    report_url = report_url['qweb-pdf'];
                    break;
                case 'controller':
                    report_url = report_url['controller'];
                    break;
                default:
                    report_url = report_url['qweb-html'];
                    break;
            }
            response = [report_url, action.report_type]

            if (action.report_type == 'qweb-html') {
                window.open(report_url, 'report', 'scrollbars=1,height=900,width=1280');
                framework.unblockUI();
            } else if (action.report_type === 'qweb-pdf') {
                // Trigger the download of the pdf/controller report
                return trigger_download(self.getSession(), response, c, action, options);
            } else if (action.report_type === 'controller') {
                return trigger_download(self.getSession(), response, c, action, options);
            }                     
        } else {
            var eval_contexts = ([session.user_context] || []).concat([action.context]);
            action.context = pyeval.eval('contexts',eval_contexts);

            // iOS devices doesn't allow iframe use the way we do it,
            // opening a new window seems the best way to workaround
            if (navigator.userAgent.match(/(iPod|iPhone|iPad)/)) {
                var params = {
                    action: JSON.stringify(action),
                    token: new Date().getTime()
                };
                var url = self.getSession().url('/web/report', params);
                framework.unblockUI();
                $('<a href="'+url+'" target="_blank"></a>')[0].click();
                return;
            }
            return trigger_download_org(self.getSession(), response, c, action, options);
        }
    }
});

});
