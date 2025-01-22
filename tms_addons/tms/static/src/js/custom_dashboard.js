/**@odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";
const actionRegistry = registry.category("actions");

class TmsDashboard extends Component {
   setup() {
        super.setup()
        this.orm = useService('orm');
        this.state = useState({
            data: {},
            draft: {},
            receiptsi: {},
            receiptstoi: {},
            receiptsc: {},
            receiptstoc: {},
            receiptstoi: {},
            trips: {},
            rkys : [],
            tkys : [],
            create_receipt : false,
            create_itans : false,
            create_trip : false,
        });
        onWillStart(() => this.loadData());
        console.log("oooooooooooooooo")
   }

    get context() {
        return this.props.context;
    }

    get domain() {
        return this.props.domain;
    }
   async loadData(){
        var self = this;

        await this.orm.call("tms.dashboard", "get_dashboard_data", [], {}).then(function(result){
            console.log("bbb", result);
            // self.state = result;
            self.state.rkys = result['rkys'];
            self.state.tkys = result['tkys'];
            self.state.draft = result['draft'];
            self.state.receiptsi = result['receiptsi'];
            self.state.receiptstoi = result['receiptstoi'];
            self.state.receiptsc = result['receiptsc'];
            self.state.receiptstoc = result['receiptstoc'];
            self.state.receiptstoi = result['receiptstoi'];
            self.state.trips = result['trips'];
            self.state.create_receipt = result['create_receipt'];
            self.state.create_itans = result['create_itans'];
            self.state.create_trip = result['create_trip'];
            
        });
        
   }
}
TmsDashboard.template = "tms.TmsDashboard";
//TmsDashboard.template = "tms.tms_dashboard";
TmsDashboard.props = {
    context: Object,
    domain: Array,
};
//  Tag name that we entered in the first step.
actionRegistry.add("tms_dashboard_custom_tag", TmsDashboard);