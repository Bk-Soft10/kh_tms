odoo.define('web.tms_branch_switch',function (require) {
    "use strict";
    var Widget = require('web.Widget');
    var SystrayMenu = require('web.SystrayMenu');
    var web_client = require('web.web_client');
    var Model = require('web.BasicModel');
    var session = require('web.session');
    window.BasicModel = Model;
    var ajax = require('web.ajax'); 

    /***************************************************************************
    Create an new 'SwitchbranchWidget' widget that allow users to switch
    from a branch to another more easily.
    ***************************************************************************/
    var SwitchBranchWidget = Widget.extend({
        sequence: 101,
        /*template:'tms.SwitchBranchWidget1',*/
        tagName: 'li',
        className: 'o_mail_navbar_item',

        /***********************************************************************
        Overload section
        ***********************************************************************/

        /**
         * Overload 'init' function to initialize the values of the widget.
         */
        init: function(parent){
            this._super(parent);
            this.branches = [];
            this.current_branch_id = 0;
            this.current_branch_name = '';
        },

        /**
         * Overload 'start' function to load datas from DB.
         */
        start: function () {
            this._super();
            this._load_data();
        },

        /**
         * Overload 'renderElement' function to set events on branch items.
         */
        renderElement: function() {
            var self = this;
            this._super();
            this.$el.show();
                
            var html = '<a class="dropdown-toggle" data-toggle="dropdown" href="#">' +
                           '<span class="oe_topbar_name">'+ this.current_branch_name +' </span> '+
                           '<b class="caret"></b>'+
                        '</a>';
        
            if ( this.branches.length === 0){
                this.$el.html(html);
            } else{
                var rend = '<ul class="dropdown-menu">';
                for (var i =0; i < this.branches.length; i++ ){
                    var branch = this.branches[i];
                    rend += '<li class="dropdown-item"> <a class="tms_branch_item" href="#" id="'+branch.id+'"> '+ branch.name +' </a></li>';
                    
                }
                rend +="</ul>";
                this.$el.html(html+rend);
                
                this.$el.find('.tms_branch_item').on('click', function(ev) {
                    var branch_id = $(ev.target).attr("id");
                    if (branch_id != self.current_branch_id){
                        var func = '/tms/switch/branch';
                        var param = {'branch_id': branch_id};
                        ajax.jsonRpc("/tms/switch/branch", 'call', param).then(function(res){
                            window.location.reload();
                        });
                    }
                });
            }
        },


        /**
         * - Load data of the branches allowed to the current users;
         * - Launch the rendering of the current widget;
         */
        _load_data: function(){
            var self = this;
            // Request for current users information
            //
            ajax.jsonRpc("/tms/user/branches", 'call').then(function(branches){ 
                self.current_branch_id = branches.current.id;
                self.current_branch_name = branches.current.name;
                var res_branch = branches.branches;
                for ( var i=0 ; i < res_branch.length; i++) {
                    var id = res_branch[i][0];
                    if(id != self.current_branch_id)
                        self.branches.push({
                            id: res_branch[i][0],
                            name: res_branch[i][1],
                        });
                }
                // Update rendering
                self.renderElement();
            });
        },

    });

SystrayMenu.Items.push(SwitchBranchWidget);

});
