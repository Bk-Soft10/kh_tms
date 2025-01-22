odoo.define('web.TmsWidgets', function (require) {
    "use strict";

    window.rrr = require;
    var core = require('web.core');
	
	window.AbstractField = require('web.AbstractField');
	window.core = require('web.core');
	var field_registry = require('web.field_registry');
	
    var FieldChar = field_registry.get('char');
    var HandleWidget = field_registry.get('html');
	
	var ajax = require('web.ajax'); 
	var allowed_plate_chars = '';
	
	ajax.jsonRpc("/get_plate_allowed_chars", 'call').then(function(value){ 
           allowed_plate_chars = value['allowed_plate_chars'];
		   if(allowed_plate_chars)
				allowed_plate_chars = allowed_plate_chars.replace(/ /g,'');
		   else 
			    allowed_plate_chars = "ابتثجحخدذرزسشعغفقصضومنكطظيabcdefghijklmnopqrstwxyzu";
			
		   console.log("allowed_plate_chars: "+allowed_plate_chars)
    }); 
	
	function changed(input, inval){
		window.plat_num= input;
		//if(ingnoreChange) return;
		
		var val = inval || (input && input.value);
		if (!val)
			return '';
		var newVal = ""; 
		var charCount = 0, ignorews = false;
		for(var j= 0; j < val.length; j++){
			var by = val.codePointAt(j);
			if(j == 0 && by == 32)
				continue;
			if(by == 32 && val.codePointAt(j-1) == 32)
				continue;
			if(by == 32){
				newVal += val.charAt(j);
				ignorews = true; 
			}
			else if((by >= 48 && by <= 57 )){
				if(charCount == 3){
					var by0 = val.codePointAt(j-1);
					if((by0 >= 48 && by0 <= 57 )){
						newVal += val.charAt(j);
					} else {
						newVal += ignorews ? val.charAt(j) : " " + val.charAt(j) ;
						ignorews = false;
					}
				}
			} else {
				if(charCount < 3){
					if(allowed_plate_chars.indexOf(val.charAt(j)) != -1){
						newVal += ignorews ? val.charAt(j) : " " + val.charAt(j);
						charCount++;
						ignorews = false;
					}
				}
			}
		}
		newVal = newVal.trim().replace("  ", " ");
		if(newVal.length > 10)
			newVal = newVal.substr(0, 10);
		if (inval)
			return newVal;
		
		input.value = newVal;
		return 	newVal;
	}

    // this is widget for unique CharField
    var PlateFieldChar = FieldChar.extend({
		start: function () {
			window.PlateFieldChar = this;
			
            this._super.apply(this, arguments)
			
			if(this.mode === 'edit'){
				var input = this.$input || this.$('input.xx_plate');
				
				function listen(){
					input.keyup(function(){
					$(this).blur();
					$(this).focus();
					});
					input.change(function(){
						changed(this);
					});
				}
				var i = 0;
				function repeat(){
					input = this.$('input.xx_plate');
					if(!input.length){
						if(i < 5)
							setTimeout(repeat, 500)
						i++;
					}else
						listen()
				}
				setTimeout(repeat, 500)
				
			}
        },
        /*
        _parseValue: function (value) {
             //trhrow exeption if not valid
        },*/
        /* 
		_getValue: function(){
			return changed(this.$input[0]);
		},*/
		
    });
    
    var BarcodeField = FieldChar.extend({
        _onChange: function () {
            this._super.apply(this, arguments);
            window.LastBar = this;
            try{
                var input = this.$('input').prevObject[0];
                input.value = '';
                this.value = '';
                input.focus();
            } catch(e){console.error(e);}
        }
    });
    /*
    var TripRouteWidget = HandleWidget.extend({
        start: function () {
            var result = this._super.apply(this, arguments)
            window.TripRoute = this
            return result;
        }
    });
    */
    
    field_registry.add('plate', PlateFieldChar);
    field_registry.add('barcode', BarcodeField);
    
    function mask_attrs(attrs) {
        var keyMask = 'data-inputmask';
        var attributes = {};
        if (keyMask in attrs)
            attributes[keyMask] = attrs[keyMask];
        else
            attributes = Object.keys(attrs).reduce(function (filtered, key) {
                if (key.indexOf(keyMask) !== -1)
                    filtered[key] = attrs[key];
                return filtered;
            }, {});
        if (!attributes)
            console.warn("The widget Mask expects the 'data-inputmask[-attribute]' attributes!");
        return attributes;
    }

    var FieldMask = FieldChar.extend({
        template: "FieldMask",
        attributes: {},
        init: function (parent, name, record, options) {
            this._super(parent, name, record, options);
            console.log("record:", this.attrs);
            this.attributes = mask_attrs(this.attrs);
        },
        render_value: function (mask) {
            this._super();
            if (this.attributes){
                if (this.$input !== undefined)
                    this.$input.inputmask(mask);
                else if ('contenteditable' in this.node.attrs)
                    this.$el.inputmask(mask);
                }
        },
    });

    var FieldMaskRegex = FieldMask.extend({
        render_value: function () {
            this._super("Regex");
        }
    });
    
    field_registry.add('mask', FieldMask);
    field_registry.add('regxmask', FieldMaskRegex);
    

});