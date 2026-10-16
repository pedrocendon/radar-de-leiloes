const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const code=fs.readFileSync(path.join(__dirname,'ui/ui.js'),'utf8');
const sandbox={};vm.createContext(sandbox);vm.runInContext(code.slice(0,code.indexOf('const $=')),sandbox);
const format=sandbox.formatPriceInput;
assert.equal(format('1000000').value,'1.000.000,00');
assert.equal(format('R$ 1.000.000,50').value,'1.000.000,50');
assert.equal(format('').value,'');
assert.equal(format('0').value,'0,00');
assert.equal(format('000123').value,'123,00');
assert.equal(format('125,5').value,'125,50');
assert.equal(format(',00',0).value,'');
const input={value:'',selectionStart:0,selectionEnd:0,listeners:{},
 addEventListener(k,f){this.listeners[k]=f;},setSelectionRange(a,b){this.selectionStart=a;this.selectionEnd=b;}};
sandbox.enablePriceFormat(input);
function type(character){
 let prevented=false;input.listeners.keydown({key:character,preventDefault(){prevented=true;}});
 if(!prevented){const a=input.selectionStart,b=input.selectionEnd;input.value=input.value.slice(0,a)+character+input.value.slice(b);input.setSelectionRange(a+1,a+1);input.listeners.input();}
}
for(const c of '1000000')type(c);
assert.equal(input.value,'1.000.000,00');assert.equal(input.selectionStart,9);
type(',');type('5');type('0');assert.equal(input.value,'1.000.000,50');
input.setSelectionRange(10,10);let prevented=false;
input.listeners.keydown({key:'Backspace',preventDefault(){prevented=true;}});
assert.equal(prevented,true);assert.equal(input.selectionStart,9);assert.equal(input.value,'1.000.000,50');
input.setSelectionRange(0,input.value.length);type('2');assert.equal(input.value,'2,00');
console.log('Formatação, digitação, centavos, colagem, seleção e separador decimal: OK.');
