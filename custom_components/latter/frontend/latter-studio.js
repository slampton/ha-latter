// AUTO-GENERATED FILE — DO NOT EDIT DIRECTLY.
var Go=globalThis,zo=Go.ShadowRoot&&(Go.ShadyCSS===void 0||Go.ShadyCSS.nativeShadow)&&"adoptedStyleSheets"in Document.prototype&&"replace"in CSSStyleSheet.prototype,Zi=Symbol(),Cn=new WeakMap,po=class{constructor(t,o,i){if(this._$cssResult$=!0,i!==Zi)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=t,this.t=o}get styleSheet(){let t=this.o,o=this.t;if(zo&&t===void 0){let i=o!==void 0&&o.length===1;i&&(t=Cn.get(o)),t===void 0&&((this.o=t=new CSSStyleSheet).replaceSync(this.cssText),i&&Cn.set(o,t))}return t}toString(){return this.cssText}},Tn=e=>new po(typeof e=="string"?e:e+"",void 0,Zi),xe=(e,...t)=>{let o=e.length===1?e[0]:t.reduce((i,a,n)=>i+(s=>{if(s._$cssResult$===!0)return s.cssText;if(typeof s=="number")return s;throw Error("Value passed to 'css' function must be a 'css' function result: "+s+". Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.")})(a)+e[n+1],e[0]);return new po(o,e,Zi)},xn=(e,t)=>{if(zo)e.adoptedStyleSheets=t.map(o=>o instanceof CSSStyleSheet?o:o.styleSheet);else for(let o of t){let i=document.createElement("style"),a=Go.litNonce;a!==void 0&&i.setAttribute("nonce",a),i.textContent=o.cssText,e.appendChild(i)}},Xi=zo?e=>e:e=>e instanceof CSSStyleSheet?(t=>{let o="";for(let i of t.cssRules)o+=i.cssText;return Tn(o)})(e):e;var{is:Dc,defineProperty:Rc,getOwnPropertyDescriptor:Lc,getOwnPropertyNames:Oc,getOwnPropertySymbols:Bc,getPrototypeOf:Nc}=Object,Ko=globalThis,An=Ko.trustedTypes,Hc=An?An.emptyScript:"",Uc=Ko.reactiveElementPolyfillSupport,mo=(e,t)=>e,Ji={toAttribute(e,t){switch(t){case Boolean:e=e?Hc:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let o=e;switch(t){case Boolean:o=e!==null;break;case Number:o=e===null?null:Number(e);break;case Object:case Array:try{o=JSON.parse(e)}catch{o=null}}return o}},In=(e,t)=>!Dc(e,t),En={attribute:!0,type:String,converter:Ji,reflect:!1,useDefault:!1,hasChanged:In};Symbol.metadata??=Symbol("metadata"),Ko.litPropertyMetadata??=new WeakMap;var et=class extends HTMLElement{static addInitializer(t){this._$Ei(),(this.l??=[]).push(t)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(t,o=En){if(o.state&&(o.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(t)&&((o=Object.create(o)).wrapped=!0),this.elementProperties.set(t,o),!o.noAccessor){let i=Symbol(),a=this.getPropertyDescriptor(t,i,o);a!==void 0&&Rc(this.prototype,t,a)}}static getPropertyDescriptor(t,o,i){let{get:a,set:n}=Lc(this.prototype,t)??{get(){return this[o]},set(s){this[o]=s}};return{get:a,set(s){let r=a?.call(this);n?.call(this,s),this.requestUpdate(t,r,i)},configurable:!0,enumerable:!0}}static getPropertyOptions(t){return this.elementProperties.get(t)??En}static _$Ei(){if(this.hasOwnProperty(mo("elementProperties")))return;let t=Nc(this);t.finalize(),t.l!==void 0&&(this.l=[...t.l]),this.elementProperties=new Map(t.elementProperties)}static finalize(){if(this.hasOwnProperty(mo("finalized")))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(mo("properties"))){let o=this.properties,i=[...Oc(o),...Bc(o)];for(let a of i)this.createProperty(a,o[a])}let t=this[Symbol.metadata];if(t!==null){let o=litPropertyMetadata.get(t);if(o!==void 0)for(let[i,a]of o)this.elementProperties.set(i,a)}this._$Eh=new Map;for(let[o,i]of this.elementProperties){let a=this._$Eu(o,i);a!==void 0&&this._$Eh.set(a,o)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(t){let o=[];if(Array.isArray(t)){let i=new Set(t.flat(1/0).reverse());for(let a of i)o.unshift(Xi(a))}else t!==void 0&&o.push(Xi(t));return o}static _$Eu(t,o){let i=o.attribute;return i===!1?void 0:typeof i=="string"?i:typeof t=="string"?t.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(t=>this.enableUpdating=t),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(t=>t(this))}addController(t){(this._$EO??=new Set).add(t),this.renderRoot!==void 0&&this.isConnected&&t.hostConnected?.()}removeController(t){this._$EO?.delete(t)}_$E_(){let t=new Map,o=this.constructor.elementProperties;for(let i of o.keys())this.hasOwnProperty(i)&&(t.set(i,this[i]),delete this[i]);t.size>0&&(this._$Ep=t)}createRenderRoot(){let t=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return xn(t,this.constructor.elementStyles),t}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(t=>t.hostConnected?.())}enableUpdating(t){}disconnectedCallback(){this._$EO?.forEach(t=>t.hostDisconnected?.())}attributeChangedCallback(t,o,i){this._$AK(t,i)}_$ET(t,o){let i=this.constructor.elementProperties.get(t),a=this.constructor._$Eu(t,i);if(a!==void 0&&i.reflect===!0){let n=(i.converter?.toAttribute!==void 0?i.converter:Ji).toAttribute(o,i.type);this._$Em=t,n==null?this.removeAttribute(a):this.setAttribute(a,n),this._$Em=null}}_$AK(t,o){let i=this.constructor,a=i._$Eh.get(t);if(a!==void 0&&this._$Em!==a){let n=i.getPropertyOptions(a),s=typeof n.converter=="function"?{fromAttribute:n.converter}:n.converter?.fromAttribute!==void 0?n.converter:Ji;this._$Em=a;let r=s.fromAttribute(o,n.type);this[a]=r??this._$Ej?.get(a)??r,this._$Em=null}}requestUpdate(t,o,i,a=!1,n){if(t!==void 0){let s=this.constructor;if(a===!1&&(n=this[t]),i??=s.getPropertyOptions(t),!((i.hasChanged??In)(n,o)||i.useDefault&&i.reflect&&n===this._$Ej?.get(t)&&!this.hasAttribute(s._$Eu(t,i))))return;this.C(t,o,i)}this.isUpdatePending===!1&&(this._$ES=this._$EP())}C(t,o,{useDefault:i,reflect:a,wrapped:n},s){i&&!(this._$Ej??=new Map).has(t)&&(this._$Ej.set(t,s??o??this[t]),n!==!0||s!==void 0)||(this._$AL.has(t)||(this.hasUpdated||i||(o=void 0),this._$AL.set(t,o)),a===!0&&this._$Em!==t&&(this._$Eq??=new Set).add(t))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(o){Promise.reject(o)}let t=this.scheduleUpdate();return t!=null&&await t,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[a,n]of this._$Ep)this[a]=n;this._$Ep=void 0}let i=this.constructor.elementProperties;if(i.size>0)for(let[a,n]of i){let{wrapped:s}=n,r=this[a];s!==!0||this._$AL.has(a)||r===void 0||this.C(a,void 0,n,r)}}let t=!1,o=this._$AL;try{t=this.shouldUpdate(o),t?(this.willUpdate(o),this._$EO?.forEach(i=>i.hostUpdate?.()),this.update(o)):this._$EM()}catch(i){throw t=!1,this._$EM(),i}t&&this._$AE(o)}willUpdate(t){}_$AE(t){this._$EO?.forEach(o=>o.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(t)),this.updated(t)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(t){return!0}update(t){this._$Eq&&=this._$Eq.forEach(o=>this._$ET(o,this[o])),this._$EM()}updated(t){}firstUpdated(t){}};et.elementStyles=[],et.shadowRootOptions={mode:"open"},et[mo("elementProperties")]=new Map,et[mo("finalized")]=new Map,Uc?.({ReactiveElement:et}),(Ko.reactiveElementVersions??=[]).push("2.1.2");var ea=globalThis,Pn=e=>e,Wo=ea.trustedTypes,Mn=Wo?Wo.createPolicy("lit-html",{createHTML:e=>e}):void 0,ta="$lit$",tt=`lit$${Math.random().toFixed(9).slice(2)}$`,oa="?"+tt,Fc=`<${oa}>`,Ct=document,_o=()=>Ct.createComment(""),ho=e=>e===null||typeof e!="object"&&typeof e!="function",ia=Array.isArray,Nn=e=>ia(e)||typeof e?.[Symbol.iterator]=="function",Qi=`[ 	
\f\r]`,go=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,Dn=/-->/g,Rn=/>/g,kt=RegExp(`>|${Qi}(?:([^\\s"'>=/]+)(${Qi}*=${Qi}*(?:[^ 	
\f\r"'\`<>=]|("|')|))|$)`,"g"),Ln=/'/g,On=/"/g,Hn=/^(?:script|style|textarea|title)$/i,aa=e=>(t,...o)=>({_$litType$:e,strings:t,values:o}),l=aa(1),Vc=aa(2),zu=aa(3),ye=Symbol.for("lit-noChange"),v=Symbol.for("lit-nothing"),Bn=new WeakMap,$t=Ct.createTreeWalker(Ct,129);function Un(e,t){if(!ia(e)||!e.hasOwnProperty("raw"))throw Error("invalid template strings array");return Mn!==void 0?Mn.createHTML(t):t}var Fn=(e,t)=>{let o=e.length-1,i=[],a,n=t===2?"<svg>":t===3?"<math>":"",s=go;for(let r=0;r<o;r++){let c=e[r],u,p,d=-1,m=0;for(;m<c.length&&(s.lastIndex=m,p=s.exec(c),p!==null);)m=s.lastIndex,s===go?p[1]==="!--"?s=Dn:p[1]!==void 0?s=Rn:p[2]!==void 0?(Hn.test(p[2])&&(a=RegExp("</"+p[2],"g")),s=kt):p[3]!==void 0&&(s=kt):s===kt?p[0]===">"?(s=a??go,d=-1):p[1]===void 0?d=-2:(d=s.lastIndex-p[2].length,u=p[1],s=p[3]===void 0?kt:p[3]==='"'?On:Ln):s===On||s===Ln?s=kt:s===Dn||s===Rn?s=go:(s=kt,a=void 0);let g=s===kt&&e[r+1].startsWith("/>")?" ":"";n+=s===go?c+Fc:d>=0?(i.push(u),c.slice(0,d)+ta+c.slice(d)+tt+g):c+tt+(d===-2?r:g)}return[Un(e,n+(e[o]||"<?>")+(t===2?"</svg>":t===3?"</math>":"")),i]},vo=class e{constructor({strings:t,_$litType$:o},i){let a;this.parts=[];let n=0,s=0,r=t.length-1,c=this.parts,[u,p]=Fn(t,o);if(this.el=e.createElement(u,i),$t.currentNode=this.el.content,o===2||o===3){let d=this.el.content.firstChild;d.replaceWith(...d.childNodes)}for(;(a=$t.nextNode())!==null&&c.length<r;){if(a.nodeType===1){if(a.hasAttributes())for(let d of a.getAttributeNames())if(d.endsWith(ta)){let m=p[s++],g=a.getAttribute(d).split(tt),_=/([.?@])?(.*)/.exec(m);c.push({type:1,index:n,name:_[2],strings:g,ctor:_[1]==="."?Yo:_[1]==="?"?Zo:_[1]==="@"?Xo:xt}),a.removeAttribute(d)}else d.startsWith(tt)&&(c.push({type:6,index:n}),a.removeAttribute(d));if(Hn.test(a.tagName)){let d=a.textContent.split(tt),m=d.length-1;if(m>0){a.textContent=Wo?Wo.emptyScript:"";for(let g=0;g<m;g++)a.append(d[g],_o()),$t.nextNode(),c.push({type:2,index:++n});a.append(d[m],_o())}}}else if(a.nodeType===8)if(a.data===oa)c.push({type:2,index:n});else{let d=-1;for(;(d=a.data.indexOf(tt,d+1))!==-1;)c.push({type:7,index:n}),d+=tt.length-1}n++}}static createElement(t,o){let i=Ct.createElement("template");return i.innerHTML=t,i}};function Tt(e,t,o=e,i){if(t===ye)return t;let a=i!==void 0?o._$Co?.[i]:o._$Cl,n=ho(t)?void 0:t._$litDirective$;return a?.constructor!==n&&(a?._$AO?.(!1),n===void 0?a=void 0:(a=new n(e),a._$AT(e,o,i)),i!==void 0?(o._$Co??=[])[i]=a:o._$Cl=a),a!==void 0&&(t=Tt(e,a._$AS(e,t.values),a,i)),t}var jo=class{constructor(t,o){this._$AV=[],this._$AN=void 0,this._$AD=t,this._$AM=o}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(t){let{el:{content:o},parts:i}=this._$AD,a=(t?.creationScope??Ct).importNode(o,!0);$t.currentNode=a;let n=$t.nextNode(),s=0,r=0,c=i[0];for(;c!==void 0;){if(s===c.index){let u;c.type===2?u=new Ft(n,n.nextSibling,this,t):c.type===1?u=new c.ctor(n,c.name,c.strings,this,t):c.type===6&&(u=new Jo(n,this,t)),this._$AV.push(u),c=i[++r]}s!==c?.index&&(n=$t.nextNode(),s++)}return $t.currentNode=Ct,a}p(t){let o=0;for(let i of this._$AV)i!==void 0&&(i.strings!==void 0?(i._$AI(t,i,o),o+=i.strings.length-2):i._$AI(t[o])),o++}},Ft=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(t,o,i,a){this.type=2,this._$AH=v,this._$AN=void 0,this._$AA=t,this._$AB=o,this._$AM=i,this.options=a,this._$Cv=a?.isConnected??!0}get parentNode(){let t=this._$AA.parentNode,o=this._$AM;return o!==void 0&&t?.nodeType===11&&(t=o.parentNode),t}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(t,o=this){t=Tt(this,t,o),ho(t)?t===v||t==null||t===""?(this._$AH!==v&&this._$AR(),this._$AH=v):t!==this._$AH&&t!==ye&&this._(t):t._$litType$!==void 0?this.$(t):t.nodeType!==void 0?this.T(t):Nn(t)?this.k(t):this._(t)}O(t){return this._$AA.parentNode.insertBefore(t,this._$AB)}T(t){this._$AH!==t&&(this._$AR(),this._$AH=this.O(t))}_(t){this._$AH!==v&&ho(this._$AH)?this._$AA.nextSibling.data=t:this.T(Ct.createTextNode(t)),this._$AH=t}$(t){let{values:o,_$litType$:i}=t,a=typeof i=="number"?this._$AC(t):(i.el===void 0&&(i.el=vo.createElement(Un(i.h,i.h[0]),this.options)),i);if(this._$AH?._$AD===a)this._$AH.p(o);else{let n=new jo(a,this),s=n.u(this.options);n.p(o),this.T(s),this._$AH=n}}_$AC(t){let o=Bn.get(t.strings);return o===void 0&&Bn.set(t.strings,o=new vo(t)),o}k(t){ia(this._$AH)||(this._$AH=[],this._$AR());let o=this._$AH,i,a=0;for(let n of t)a===o.length?o.push(i=new e(this.O(_o()),this.O(_o()),this,this.options)):i=o[a],i._$AI(n),a++;a<o.length&&(this._$AR(i&&i._$AB.nextSibling,a),o.length=a)}_$AR(t=this._$AA.nextSibling,o){for(this._$AP?.(!1,!0,o);t!==this._$AB;){let i=Pn(t).nextSibling;Pn(t).remove(),t=i}}setConnected(t){this._$AM===void 0&&(this._$Cv=t,this._$AP?.(t))}},xt=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(t,o,i,a,n){this.type=1,this._$AH=v,this._$AN=void 0,this.element=t,this.name=o,this._$AM=a,this.options=n,i.length>2||i[0]!==""||i[1]!==""?(this._$AH=Array(i.length-1).fill(new String),this.strings=i):this._$AH=v}_$AI(t,o=this,i,a){let n=this.strings,s=!1;if(n===void 0)t=Tt(this,t,o,0),s=!ho(t)||t!==this._$AH&&t!==ye,s&&(this._$AH=t);else{let r=t,c,u;for(t=n[0],c=0;c<n.length-1;c++)u=Tt(this,r[i+c],o,c),u===ye&&(u=this._$AH[c]),s||=!ho(u)||u!==this._$AH[c],u===v?t=v:t!==v&&(t+=(u??"")+n[c+1]),this._$AH[c]=u}s&&!a&&this.j(t)}j(t){t===v?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,t??"")}},Yo=class extends xt{constructor(){super(...arguments),this.type=3}j(t){this.element[this.name]=t===v?void 0:t}},Zo=class extends xt{constructor(){super(...arguments),this.type=4}j(t){this.element.toggleAttribute(this.name,!!t&&t!==v)}},Xo=class extends xt{constructor(t,o,i,a,n){super(t,o,i,a,n),this.type=5}_$AI(t,o=this){if((t=Tt(this,t,o,0)??v)===ye)return;let i=this._$AH,a=t===v&&i!==v||t.capture!==i.capture||t.once!==i.once||t.passive!==i.passive,n=t!==v&&(i===v||a);a&&this.element.removeEventListener(this.name,this,i),n&&this.element.addEventListener(this.name,this,t),this._$AH=t}handleEvent(t){typeof this._$AH=="function"?this._$AH.call(this.options?.host??this.element,t):this._$AH.handleEvent(t)}},Jo=class{constructor(t,o,i){this.element=t,this.type=6,this._$AN=void 0,this._$AM=o,this.options=i}get _$AU(){return this._$AM._$AU}_$AI(t){Tt(this,t)}},Vn={M:ta,P:tt,A:oa,C:1,L:Fn,R:jo,D:Nn,V:Tt,I:Ft,H:xt,N:Zo,U:Xo,B:Yo,F:Jo},qc=ea.litHtmlPolyfillSupport;qc?.(vo,Ft),(ea.litHtmlVersions??=[]).push("3.3.3");var na=(e,t,o)=>{let i=o?.renderBefore??t,a=i._$litPart$;if(a===void 0){let n=o?.renderBefore??null;i._$litPart$=a=new Ft(t.insertBefore(_o(),n),n,void 0,o??{})}return a._$AI(e),a};var sa=globalThis,ot=class extends et{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let t=super.createRenderRoot();return this.renderOptions.renderBefore??=t.firstChild,t}update(t){let o=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(t),this._$Do=na(o,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return ye}};ot._$litElement$=!0,ot.finalized=!0,sa.litElementHydrateSupport?.({LitElement:ot});var Gc=sa.litElementPolyfillSupport;Gc?.({LitElement:ot});(sa.litElementVersions??=[]).push("4.2.2");var Ae={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ct=e=>(...t)=>({_$litDirective$:e,values:t}),je=class{constructor(t){}get _$AU(){return this._$AM._$AU}_$AT(t,o,i){this._$Ct=t,this._$AM=o,this._$Ci=i}_$AS(t,o){return this.update(t,o)}update(t,o){return this.render(...o)}};var{I:zc}=Vn,qn=e=>e;var zn=e=>e.strings===void 0,Gn=()=>document.createComment(""),Vt=(e,t,o)=>{let i=e._$AA.parentNode,a=t===void 0?e._$AB:t._$AA;if(o===void 0){let n=i.insertBefore(Gn(),a),s=i.insertBefore(Gn(),a);o=new zc(n,s,e,e.options)}else{let n=o._$AB.nextSibling,s=o._$AM,r=s!==e;if(r){let c;o._$AQ?.(e),o._$AM=e,o._$AP!==void 0&&(c=e._$AU)!==s._$AU&&o._$AP(c)}if(n!==a||r){let c=o._$AA;for(;c!==n;){let u=qn(c).nextSibling;qn(i).insertBefore(c,a),c=u}}}return o},dt=(e,t,o=e)=>(e._$AI(t,o),e),Kc={},Qo=(e,t=Kc)=>e._$AH=t,Kn=e=>e._$AH,ei=e=>{e._$AR(),e._$AA.remove()};var S=ct(class extends je{constructor(e){if(super(e),e.type!==Ae.PROPERTY&&e.type!==Ae.ATTRIBUTE&&e.type!==Ae.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!zn(e))throw Error("`live` bindings can only contain a single expression")}render(e){return e}update(e,[t]){if(t===ye||t===v)return t;let o=e.element,i=e.name;if(e.type===Ae.PROPERTY){if(t===o[i])return ye}else if(e.type===Ae.BOOLEAN_ATTRIBUTE){if(!!t===o.hasAttribute(i))return ye}else if(e.type===Ae.ATTRIBUTE&&o.getAttribute(i)===t+"")return ye;return Qo(e),t}});var Wn=(e,t,o)=>{let i=new Map;for(let a=t;a<=o;a++)i.set(e[a],a);return i},ra=ct(class extends je{constructor(e){if(super(e),e.type!==Ae.CHILD)throw Error("repeat() can only be used in text expressions")}dt(e,t,o){let i;o===void 0?o=t:t!==void 0&&(i=t);let a=[],n=[],s=0;for(let r of e)a[s]=i?i(r,s):s,n[s]=o(r,s),s++;return{values:n,keys:a}}render(e,t,o){return this.dt(e,t,o).values}update(e,[t,o,i]){let a=Kn(e),{values:n,keys:s}=this.dt(t,o,i);if(!Array.isArray(a))return this.ut=s,n;let r=this.ut??=[],c=[],u,p,d=0,m=a.length-1,g=0,_=n.length-1;for(;d<=m&&g<=_;)if(a[d]===null)d++;else if(a[m]===null)m--;else if(r[d]===s[g])c[g]=dt(a[d],n[g]),d++,g++;else if(r[m]===s[_])c[_]=dt(a[m],n[_]),m--,_--;else if(r[d]===s[_])c[_]=dt(a[d],n[_]),Vt(e,c[_+1],a[d]),d++,_--;else if(r[m]===s[g])c[g]=dt(a[m],n[g]),Vt(e,a[d],a[m]),m--,g++;else if(u===void 0&&(u=Wn(s,g,_),p=Wn(r,d,m)),u.has(r[d]))if(u.has(r[m])){let h=p.get(s[g]),b=h!==void 0?a[h]:null;if(b===null){let y=Vt(e,a[d]);dt(y,n[g]),c[g]=y}else c[g]=dt(b,n[g]),Vt(e,a[d],b),a[h]=null;g++}else ei(a[m]),m--;else ei(a[d]),d++;for(;g<=_;){let h=Vt(e,c[_+1]);dt(h,n[g]),c[g++]=h}for(;d<=m;){let h=a[d++];h!==null&&ei(h)}return this.ut=s,Qo(e,c),ye}});var Wc=new Set(["button","checkbox","color","file","hidden","image","radio","range","reset","submit"]);function jc(e){if(!e)return!1;let t=e.tagName;if(t!=="INPUT"&&t!=="TEXTAREA")return!1;if(t==="INPUT"){let i=(e.type||"text").toLowerCase();if(Wc.has(i))return!1}let o=typeof e.getRootNode=="function"?e.getRootNode():null;return o&&typeof o=="object"&&"activeElement"in o?o.activeElement===e:typeof document<"u"&&document.activeElement===e}var la=class extends je{_initialized=!1;constructor(t){if(super(t),t.type!==Ae.PROPERTY&&t.type!==Ae.ATTRIBUTE)throw new Error("focusSafe() can only be used in property or attribute bindings")}render(t){return t===v||t===null||t===void 0?"":t}update(t,[o]){let i=o===v||o===null||o===void 0?"":o;if(this._initialized&&"element"in t&&jc(t.element))return ye;if(this._initialized=!0,"element"in t&&t.type===Ae.PROPERTY){let a=t.element;return a[t.name]!==i&&(a[t.name]=i),ye}return i}},V=ct(la);function ge(e,t,o){if(o===void 0)return ra(e,t);let i=t,a=new Map;return ra(e,(s,r)=>{r===0&&a.clear();let c=i(s,r),u=a.get(c)??0;return a.set(c,u+1),u===0?c:`${String(c)}__dup_${u}`},o)}var ca=["restart","find_my","activate_screensaver","deactivate_screensaver","wake_screen","screen_off","set_profiler_on","set_profiler_off","request_telemetry","trigger_va","dismiss_ringing","cancel_timer","reset_stopwatch"],bo=new Set(["set_ble_scanner_offset","set_area_fusion","set_area_illuminance","calibrate_area_illuminance","capture_ble_area_signature","clear_ble_area_signature","send_announcement","check_system_updates","clear_internal_logs","remove_device","add_latter_device","ignore_discovered_device","unignore_discovered_device","add_ble_device","create_device_group","delete_device_group","update_group_baseline","apply_batch_device_setting","test_doorbell_speaker","mint_camera_preview_url","delete_photo","create_photo_collection","rename_photo_collection","delete_photo_collection","update_photo_metadata","bulk_update_photos","browse_media_folder","import_media_photos","save_system_config","rotate_signing_key","set_security_pin"]),da=new Set(["esphome_entity_action","device_action","set_device_photo_pool","save_device_config"]),Be=[{token:"app:pinned",label:"Pinned",group:"Apps",dockOnly:!0},{token:"app:music",label:"Music",group:"Apps"},{token:"app:home_hub",label:"Home Hub",group:"Apps"},{token:"app:cameras",label:"Cameras",group:"Apps"},{token:"app:area",label:"Area Control",group:"Apps"},{token:"app:remote",label:"Remote",group:"Apps"},{token:"app:weather",label:"Sky & Weather",group:"Apps"},{token:"app:time",label:"Time",group:"Apps"},{token:"app:calendar",label:"Calendar",group:"Apps"},{token:"app:tools",label:"Tools",group:"Apps"},{token:"app:games",label:"Games",group:"Apps"},{token:"app:clock",label:"Clock Face",group:"Apps"},{token:"home_hub:alarm",label:"Security Alarm",group:"Home Hub"},{token:"home_hub:intercom",label:"Broadcast",group:"Home Hub"},{token:"home_hub:thermostat",label:"Thermostat",group:"Home Hub"},{token:"home_hub:entry",label:"Entry & Garage",group:"Home Hub"},{token:"home_hub:vacuum",label:"Robot Vacuum",group:"Home Hub"},{token:"cameras:grid",label:"Cameras: Grid",group:"Cameras"},{token:"cameras:single",label:"Cameras: Live",group:"Cameras"},{token:"cameras:carousel",label:"Cameras: Carousel",group:"Cameras"},{token:"cameras:settings",label:"Cameras: Settings",group:"Cameras"},{token:"area:picker",label:"Switch Area",group:"Area Control"},{token:"area:scene",label:"Area: Scenes",group:"Area Control"},{token:"area:light",label:"Area: Lights",group:"Area Control"},{token:"area:cover",label:"Area: Blinds & Curtains",group:"Area Control"},{token:"area:fan",label:"Area: Fans",group:"Area Control"},{token:"area:switch",label:"Area: Switches",group:"Area Control"},{token:"area:climate",label:"Area: Climate",group:"Area Control"},{token:"area:media",label:"Area: Media",group:"Area Control"},{token:"area:all",label:"Area: All Devices",group:"Area Control"},{token:"weather:current",label:"Current Weather",group:"Sky & Weather"},{token:"weather:forecast",label:"5-Day Forecast",group:"Sky & Weather"},{token:"weather:sun",label:"Sun Path",group:"Sky & Weather"},{token:"weather:moon",label:"Moon Phase",group:"Sky & Weather"},{token:"time:clock",label:"World Clocks",group:"Time"},{token:"time:timers",label:"Timers",group:"Time"},{token:"time:alarms",label:"Alarms",group:"Time"},{token:"time:stopwatch",label:"Stopwatch",group:"Time"},{token:"calendar:overview",label:"Upcoming Events",group:"Calendar"},{token:"calendar:day",label:"Day View",group:"Calendar"},{token:"calendar:week",label:"Week View",group:"Calendar"},{token:"calendar:month",label:"Month View",group:"Calendar"},{token:"music:speakers",label:"Speakers",group:"Music"},{token:"music:library",label:"Music Library",group:"Music"},{token:"music:favorites",label:"Favorites",group:"Music"},{token:"music:playlists",label:"Playlists",group:"Music"},{token:"music:queue",label:"Playback Queue",group:"Music"},{token:"music:album_tracks",label:"Album Tracks",group:"Music"},{token:"music:lyrics",label:"Music Lyrics",group:"Music"},{token:"music:info",label:"Track Info",group:"Music"},{token:"remote:devices",label:"Remote Devices",group:"Remote"},{token:"tools:stopwatch",label:"Analog Chronograph",group:"Tools",capability:"round"},{token:"tools:level",label:"Bubble Level",group:"Tools",capability:"imu"},{token:"tools:flashlight",label:"Flashlight",group:"Tools"},{token:"tools:calculator",label:"Calculator",group:"Tools"},{token:"tools:dice",label:"Dice Roll",group:"Tools"},{token:"tools:coin_flip",label:"Coin Flip",group:"Tools"},{token:"games:marbles",label:"Marbles",group:"Games"},{token:"games:archery",label:"Archery",group:"Games"},{token:"games:bricks",label:"Bricks",group:"Games"},{token:"games:chomp",label:"Chomp",group:"Games"},{token:"games:2048",label:"2048",group:"Games"},{token:"games:memory",label:"Memory Match",group:"Games"},{token:"settings:display",label:"Display Settings",group:"Settings"},{token:"settings:sleep",label:"Sleep & Wake",group:"Settings"},{token:"settings:sound",label:"Sound Settings",group:"Settings"},{token:"settings:voice",label:"Voice Settings",group:"Settings"},{token:"settings:music",label:"Music Settings",group:"Settings"},{token:"settings:home",label:"Home Settings",group:"Settings"},{token:"settings:actions",label:"Device Actions",group:"Settings"},{token:"settings:update",label:"Software Update",group:"Settings"},{token:"settings:info",label:"System Info",group:"Settings"}],ut=[{token:"calendar",label:"Calendar"},{token:"music_queue",label:"Music Queue"},{token:"stopwatch",label:"Stopwatch"},{token:"alarms",label:"Alarms"},{token:"timers",label:"Timers"}],At=[{token:"scene",label:"Scenes"},{token:"light",label:"Lights"},{token:"cover",label:"Blinds & Curtains"},{token:"fan",label:"Fans"},{token:"switch",label:"Switches"},{token:"climate",label:"Climate"},{token:"media",label:"Media"},{token:"all",label:"All Devices"}],Et=[{token:"alarm",label:"Security Alarm"},{token:"intercom",label:"Broadcast"},{token:"thermostat",label:"Thermostat"},{token:"entry",label:"Entry & Garage"},{token:"vacuum",label:"Robot Vacuum"}],it=[{token:"stopwatch",label:"Analog Chronograph",capability:"round"},{token:"level",label:"Bubble Level",capability:"imu"},{token:"flashlight",label:"Flashlight"},{token:"calculator",label:"Calculator"},{token:"dice",label:"Dice Roll"},{token:"coin_flip",label:"Coin Flip"}],It=[{token:"marbles",label:"Marbles"},{token:"archery",label:"Archery"},{token:"bricks",label:"Bricks"},{token:"chomp",label:"Chomp"},{token:"2048",label:"2048"},{token:"memory",label:"Memory Match"}],ti=[{token:"glass",label:"Frosted glass"},{token:"inverted",label:"Inverted badge"}],oi=[{token:"default",label:"Default"},{token:"primary",label:"Theme"},{token:"gold",label:"Amber"},{token:"green",label:"Green"},{token:"red",label:"Red"},{token:"orange",label:"Orange"}],ua=[{iana:"Etc/GMT+12",city:"UTC-12",label:"UTC-12:00 \u2014 International Date Line West",std_off:-720,dst_off:-720,std_abbr:"UTC-12",dst_abbr:"UTC-12",rule:"none"},{iana:"Pacific/Pago_Pago",city:"Pago Pago",label:"UTC-11:00 \u2014 Samoa Standard Time (SST)",std_off:-660,dst_off:-660,std_abbr:"SST",dst_abbr:"SST",rule:"none"},{iana:"Pacific/Honolulu",city:"Honolulu",label:"UTC-10:00 \u2014 Hawaii-Aleutian Standard Time (HST)",std_off:-600,dst_off:-600,std_abbr:"HST",dst_abbr:"HST",rule:"none"},{iana:"Pacific/Marquesas",city:"Marquesas",label:"UTC-09:30 \u2014 Marquesas Time (MART)",std_off:-570,dst_off:-570,std_abbr:"MART",dst_abbr:"MART",rule:"none"},{iana:"America/Anchorage",city:"Anchorage",label:"UTC-09:00 \u2014 Alaska Time (AKST/AKDT)",std_off:-540,dst_off:-480,std_abbr:"AKST",dst_abbr:"AKDT",rule:"us"},{iana:"America/Los_Angeles",city:"Los Angeles",label:"UTC-08:00 \u2014 Pacific Time (PST/PDT)",std_off:-480,dst_off:-420,std_abbr:"PST",dst_abbr:"PDT",rule:"us"},{iana:"Etc/GMT+8",city:"UTC-8",label:"UTC-08:00 \u2014 Coordinated Universal Time-08 (No DST)",std_off:-480,dst_off:-480,std_abbr:"UTC-8",dst_abbr:"UTC-8",rule:"none"},{iana:"America/Denver",city:"Denver",label:"UTC-07:00 \u2014 Mountain Time (MST/MDT)",std_off:-420,dst_off:-360,std_abbr:"MST",dst_abbr:"MDT",rule:"us"},{iana:"America/Phoenix",city:"Phoenix",label:"UTC-07:00 \u2014 Mountain Standard Time (MST, No DST)",std_off:-420,dst_off:-420,std_abbr:"MST",dst_abbr:"MST",rule:"none"},{iana:"America/Chicago",city:"Chicago",label:"UTC-06:00 \u2014 Central Time (CST/CDT)",std_off:-360,dst_off:-300,std_abbr:"CST",dst_abbr:"CDT",rule:"us"},{iana:"America/Regina",city:"Regina",label:"UTC-06:00 \u2014 Central Standard Time (CST, No DST)",std_off:-360,dst_off:-360,std_abbr:"CST",dst_abbr:"CST",rule:"none"},{iana:"America/New_York",city:"New York",label:"UTC-05:00 \u2014 Eastern Time (EST/EDT)",std_off:-300,dst_off:-240,std_abbr:"EST",dst_abbr:"EDT",rule:"us"},{iana:"America/Lima",city:"Lima",label:"UTC-05:00 \u2014 Eastern Standard Time (EST, No DST)",std_off:-300,dst_off:-300,std_abbr:"EST",dst_abbr:"EST",rule:"none"},{iana:"America/Halifax",city:"Halifax",label:"UTC-04:00 \u2014 Atlantic Time (AST/ADT)",std_off:-240,dst_off:-180,std_abbr:"AST",dst_abbr:"ADT",rule:"us"},{iana:"America/Puerto_Rico",city:"Puerto Rico",label:"UTC-04:00 \u2014 Atlantic Standard Time (AST, No DST)",std_off:-240,dst_off:-240,std_abbr:"AST",dst_abbr:"AST",rule:"none"},{iana:"America/St_Johns",city:"St. John's",label:"UTC-03:30 \u2014 Newfoundland Time (NST/NDT)",std_off:-210,dst_off:-150,std_abbr:"NST",dst_abbr:"NDT",rule:"us"},{iana:"America/Sao_Paulo",city:"Sao Paulo",label:"UTC-03:00 \u2014 South America Eastern Time (BRT/ART)",std_off:-180,dst_off:-180,std_abbr:"BRT",dst_abbr:"BRT",rule:"none"},{iana:"Etc/GMT+2",city:"UTC-2",label:"UTC-02:00 \u2014 Coordinated Universal Time-02",std_off:-120,dst_off:-120,std_abbr:"UTC-2",dst_abbr:"UTC-2",rule:"none"},{iana:"Atlantic/Azores",city:"Azores",label:"UTC-01:00 \u2014 Azores Time (AZOT/AZOST)",std_off:-60,dst_off:0,std_abbr:"AZOT",dst_abbr:"AZOST",rule:"eu"},{iana:"Atlantic/Cape_Verde",city:"Cape Verde",label:"UTC-01:00 \u2014 Cape Verde Time (CVT, No DST)",std_off:-60,dst_off:-60,std_abbr:"CVT",dst_abbr:"CVT",rule:"none"},{iana:"Atlantic/Reykjavik",city:"Reykjavik",label:"UTC+00:00 \u2014 Greenwich Mean Time (GMT, No DST)",std_off:0,dst_off:0,std_abbr:"GMT",dst_abbr:"GMT",rule:"none"},{iana:"Europe/London",city:"London",label:"UTC+00:00 \u2014 Western European Time (GMT/BST)",std_off:0,dst_off:60,std_abbr:"GMT",dst_abbr:"BST",rule:"eu"},{iana:"Europe/Berlin",city:"Berlin",label:"UTC+01:00 \u2014 Central European Time (CET/CEST)",std_off:60,dst_off:120,std_abbr:"CET",dst_abbr:"CEST",rule:"eu"},{iana:"Africa/Lagos",city:"Lagos",label:"UTC+01:00 \u2014 West Africa Time (WAT, No DST)",std_off:60,dst_off:60,std_abbr:"WAT",dst_abbr:"WAT",rule:"none"},{iana:"Europe/Athens",city:"Athens",label:"UTC+02:00 \u2014 Eastern European Time (EET/EEST)",std_off:120,dst_off:180,std_abbr:"EET",dst_abbr:"EEST",rule:"eu"},{iana:"Africa/Johannesburg",city:"Johannesburg",label:"UTC+02:00 \u2014 Central / South Africa Time (CAT/SAST)",std_off:120,dst_off:120,std_abbr:"SAST",dst_abbr:"SAST",rule:"none"},{iana:"Asia/Riyadh",city:"Riyadh",label:"UTC+03:00 \u2014 Arabia / East Africa Time (AST/EAT)",std_off:180,dst_off:180,std_abbr:"AST",dst_abbr:"AST",rule:"none"},{iana:"Asia/Tehran",city:"Tehran",label:"UTC+03:30 \u2014 Iran Standard Time (IRST)",std_off:210,dst_off:210,std_abbr:"IRST",dst_abbr:"IRST",rule:"none"},{iana:"Asia/Dubai",city:"Dubai",label:"UTC+04:00 \u2014 Gulf Standard Time (GST)",std_off:240,dst_off:240,std_abbr:"GST",dst_abbr:"GST",rule:"none"},{iana:"Asia/Kabul",city:"Kabul",label:"UTC+04:30 \u2014 Afghanistan Time (AFT)",std_off:270,dst_off:270,std_abbr:"AFT",dst_abbr:"AFT",rule:"none"},{iana:"Asia/Karachi",city:"Karachi",label:"UTC+05:00 \u2014 Pakistan / West Asia Time (PKT)",std_off:300,dst_off:300,std_abbr:"PKT",dst_abbr:"PKT",rule:"none"},{iana:"Asia/Kolkata",city:"Kolkata",label:"UTC+05:30 \u2014 India / Sri Lanka Standard Time (IST)",std_off:330,dst_off:330,std_abbr:"IST",dst_abbr:"IST",rule:"none"},{iana:"Asia/Kathmandu",city:"Kathmandu",label:"UTC+05:45 \u2014 Nepal Time (NPT)",std_off:345,dst_off:345,std_abbr:"NPT",dst_abbr:"NPT",rule:"none"},{iana:"Asia/Dhaka",city:"Dhaka",label:"UTC+06:00 \u2014 Bangladesh / Central Asia Time (BST)",std_off:360,dst_off:360,std_abbr:"BST",dst_abbr:"BST",rule:"none"},{iana:"Asia/Yangon",city:"Yangon",label:"UTC+06:30 \u2014 Myanmar Time (MMT)",std_off:390,dst_off:390,std_abbr:"MMT",dst_abbr:"MMT",rule:"none"},{iana:"Asia/Bangkok",city:"Bangkok",label:"UTC+07:00 \u2014 Indochina Time (ICT)",std_off:420,dst_off:420,std_abbr:"ICT",dst_abbr:"ICT",rule:"none"},{iana:"Asia/Singapore",city:"Singapore",label:"UTC+08:00 \u2014 China / Singapore / AWST (CST/SGT/AWST)",std_off:480,dst_off:480,std_abbr:"SGT",dst_abbr:"SGT",rule:"none"},{iana:"Australia/Eucla",city:"Eucla",label:"UTC+08:45 \u2014 Australian Central Western Time (ACWST)",std_off:525,dst_off:525,std_abbr:"ACWST",dst_abbr:"ACWST",rule:"none"},{iana:"Asia/Tokyo",city:"Tokyo",label:"UTC+09:00 \u2014 Japan / Korea Standard Time (JST/KST)",std_off:540,dst_off:540,std_abbr:"JST",dst_abbr:"JST",rule:"none"},{iana:"Australia/Adelaide",city:"Adelaide",label:"UTC+09:30 \u2014 Australian Central Time (ACST/ACDT)",std_off:570,dst_off:630,std_abbr:"ACST",dst_abbr:"ACDT",rule:"au"},{iana:"Australia/Darwin",city:"Darwin",label:"UTC+09:30 \u2014 Australian Central Standard Time (ACST, No DST)",std_off:570,dst_off:570,std_abbr:"ACST",dst_abbr:"ACST",rule:"none"},{iana:"Australia/Sydney",city:"Sydney",label:"UTC+10:00 \u2014 Australian Eastern Time (AEST/AEDT)",std_off:600,dst_off:660,std_abbr:"AEST",dst_abbr:"AEDT",rule:"au"},{iana:"Australia/Brisbane",city:"Brisbane",label:"UTC+10:00 \u2014 Australian Eastern Standard Time (AEST, No DST)",std_off:600,dst_off:600,std_abbr:"AEST",dst_abbr:"AEST",rule:"none"},{iana:"Australia/Lord_Howe",city:"Lord Howe",label:"UTC+10:30 \u2014 Lord Howe Time (LHST/LHDT)",std_off:630,dst_off:660,std_abbr:"LHST",dst_abbr:"LHDT",rule:"au30"},{iana:"Pacific/Guadalcanal",city:"Guadalcanal",label:"UTC+11:00 \u2014 Solomon Islands / New Caledonia Time (SBT)",std_off:660,dst_off:660,std_abbr:"SBT",dst_abbr:"SBT",rule:"none"},{iana:"Pacific/Auckland",city:"Auckland",label:"UTC+12:00 \u2014 New Zealand Time (NZST/NZDT)",std_off:720,dst_off:780,std_abbr:"NZST",dst_abbr:"NZDT",rule:"nz"},{iana:"Etc/GMT-12",city:"UTC+12",label:"UTC+12:00 \u2014 Coordinated Universal Time+12 (No DST)",std_off:720,dst_off:720,std_abbr:"UTC+12",dst_abbr:"UTC+12",rule:"none"},{iana:"Pacific/Chatham",city:"Chatham",label:"UTC+12:45 \u2014 Chatham Islands Time (CHAST/CHADT)",std_off:765,dst_off:825,std_abbr:"CHAST",dst_abbr:"CHADT",rule:"nz"},{iana:"Pacific/Tongatapu",city:"Tongatapu",label:"UTC+13:00 \u2014 Tonga / Phoenix Islands Time (TOT)",std_off:780,dst_off:780,std_abbr:"TOT",dst_abbr:"TOT",rule:"none"},{iana:"Pacific/Kiritimati",city:"Kiritimati",label:"UTC+14:00 \u2014 Line Islands Time (LINT)",std_off:840,dst_off:840,std_abbr:"LINT",dst_abbr:"LINT",rule:"none"}],jn=[{key:"wake_word_mode",label:"Wake Word Mode",domain:"select",default:"Docked Only",section:"audio",group_tier:"behavior",options:["Docked Only","Always On","Disabled"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"tap_to_wake",label:"Tap to Wake",domain:"select",default:"Docked Only",section:"power",group_tier:"behavior",options:["Single Tap","Double Tap","Docked Only","Disabled"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"pickup_to_wake",label:"Pickup to Wake",domain:"select",default:"Docked Only",section:"power",group_tier:"behavior",options:["Always On","Docked Only","Disabled"],min:null,max:null,step:null,unit:"",capability:"display_imu"},{key:"battery_screen_timeout",label:"Battery Screen Timeout",domain:"select",default:"30s",section:"power",group_tier:"behavior",options:["10s","15s","30s","1 min","2 min","Never"],min:null,max:null,step:null,unit:"",capability:"display_battery"},{key:"docked_idle_timeout",label:"Docked Idle Timeout",domain:"select",default:"1 min",section:"display",group_tier:"behavior",options:["10s","15s","30s","1 min","2 min","5 min","Never"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"battery_hibernate_timeout",label:"Battery Hibernate Timeout",domain:"select",default:"15 min",section:"power",group_tier:"behavior",options:["5 min","10 min","15 min","30 min","Disabled"],min:null,max:null,step:null,unit:"",capability:"display_battery"},{key:"screensaver_mode",label:"Screensaver mode",domain:"select",default:"Docked Only",section:"display",group_tier:"behavior",options:["Docked Only","Always","Never"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"screensaver_style",label:"Screensaver Style",domain:"select",default:"Ambient Clock",section:"display",group_tier:"display",options:["Ambient Clock","Photo Frame","Aurora","Starfield","Digital Rain","Fireworks"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"auto_brightness_mode",label:"Auto Brightness Mode",domain:"select",default:"Sun Synchronized",section:"display",group_tier:"behavior",options:["Disabled","Sun Synchronized","Time Schedule","Ambient Light"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"manual_brightness",label:"Manual Brightness",domain:"number",default:80,section:"display",group_tier:"behavior",options:[],min:1,max:100,step:1,unit:"%",capability:"display"},{key:"day_brightness",label:"Day Brightness",domain:"number",default:90,section:"display",group_tier:"behavior",options:[],min:1,max:100,step:1,unit:"%",capability:"display"},{key:"night_brightness",label:"Night Brightness",domain:"number",default:35,section:"display",group_tier:"behavior",options:[],min:1,max:100,step:1,unit:"%",capability:"display"},{key:"day_start_hour",label:"Day Start Hour",domain:"number",default:7,section:"display",group_tier:"behavior",options:[],min:0,max:23,step:1,unit:":00",capability:"display"},{key:"night_start_hour",label:"Night Start Hour",domain:"number",default:20,section:"display",group_tier:"behavior",options:[],min:0,max:23,step:1,unit:":00",capability:"display"},{key:"color_profile",label:"Color Profile",domain:"select",default:"Steel Blue",section:"display",group_tier:"display",options:["Steel Blue","Pink","Blue","Green","Custom"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"va_visual_profile",label:"Visual Profile",domain:"select",default:"Nebula",section:"display",group_tier:"display",options:["Nebula","Solaris","Rings","Light Bar","Dot Wave"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"home_screen_enabled",label:"Enable Home Screen",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"start_screen",label:"Start Screen",domain:"select",default:"Home",section:"interface",group_tier:"interface",options:["Home","Pinned","Time App","Calendar","Clock Face","Media","Home Hub","Area Controls","Remote","Weather","Cameras","Games","Tools"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"return_to_home_timeout",label:"Return to Home Timeout",domain:"select",default:"2 min",section:"interface",group_tier:"interface",options:["15s","30s","1 min","2 min","5 min","10 min","Never"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"clock_face",label:"Clock Face",domain:"select",default:"Minimal Digital",section:"interface",group_tier:"interface",options:["Minimal Digital","Modern Analog","Hybrid Digital"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"time_format",label:"Time Format",domain:"select",default:"12-Hour (AM/PM)",section:"interface",group_tier:"interface",options:["12-Hour (AM/PM)","24-Hour"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"weather_background",label:"Weather Background",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"home_sun",label:"Sun",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"home_moon",label:"Moon",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"wake_greeting",label:"Wake Greeting",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"album_art_style",label:"Album Art Style",domain:"select",default:"Full Screen",section:"interface",group_tier:"interface",options:["Full Screen","Letterbox","Standard","None"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"music_overlay_style",label:"Overlay Style",domain:"select",default:"Art + Metadata",section:"interface",group_tier:"interface",options:["Art Only","Art + Metadata","Always Visible"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"music_auto_open",label:"Auto-open on play",domain:"select",default:"Now Playing",section:"interface",group_tier:"interface",options:["Now Playing","Lyrics","Off"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"album_sort_order",label:"Album Sort Order",domain:"select",default:"Alphabetical",section:"interface",group_tier:"interface",options:["Alphabetical","Newest on Top","Oldest on Top"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"artist_album_sort_order",label:"Artist Album Sort Order",domain:"select",default:"Oldest on Top",section:"interface",group_tier:"interface",options:["Oldest on Top","Newest on Top","Alphabetical"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"podcast_sort_order",label:"Podcast Sort Order",domain:"select",default:"Newest on Top",section:"interface",group_tier:"interface",options:["Newest on Top","Oldest on Top"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"ww_sens_okay_nabu",label:"Okay Nabu Sensitivity",domain:"select",default:"Moderately sensitive",section:"audio",group_tier:"behavior",options:["Slightly sensitive","Moderately sensitive","Very sensitive"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"ww_sens_hey_luna",label:"Hey Luna Sensitivity",domain:"select",default:"Moderately sensitive",section:"audio",group_tier:"behavior",options:["Slightly sensitive","Moderately sensitive","Very sensitive"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"ww_sens_hey_jarvis",label:"Hey Jarvis Sensitivity",domain:"select",default:"Moderately sensitive",section:"audio",group_tier:"behavior",options:["Slightly sensitive","Moderately sensitive","Very sensitive"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"ww_sens_hey_mycroft",label:"Hey Mycroft Sensitivity",domain:"select",default:"Moderately sensitive",section:"audio",group_tier:"behavior",options:["Slightly sensitive","Moderately sensitive","Very sensitive"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"ww_sens_alexa",label:"Alexa Sensitivity",domain:"select",default:"Moderately sensitive",section:"audio",group_tier:"behavior",options:["Slightly sensitive","Moderately sensitive","Very sensitive"],min:null,max:null,step:null,unit:"",capability:"mic"},{key:"wake_screen_on_assist",label:"Wake Screen on Assist",domain:"switch",default:!0,section:"audio",group_tier:"behavior",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"alert_volume",label:"Alert Volume",domain:"number",default:80,section:"audio",group_tier:"behavior",options:[],min:20,max:100,step:5,unit:"%",capability:"speaker"},{key:"volume_step_size",label:"Volume Step Size",domain:"number",default:5,section:"audio",group_tier:"behavior",options:[],min:1,max:10,step:1,unit:"%",capability:"speaker"},{key:"game_sound_effects",label:"Game Sound Effects",domain:"switch",default:!0,section:"audio",group_tier:"behavior",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"ble_beacon_mode",label:"BLE Beacon Mode",domain:"select",default:"Handheld Only",section:"presence",group_tier:"behavior",options:["Handheld Only","Handheld + Screen Off","Always"],min:null,max:null,step:null,unit:"",capability:"beacon_battery"},{key:"weather_sim_condition",label:"Weather Simulation",domain:"select",default:"Live (Home Assistant)",section:"developer",group_tier:null,options:["Live (Home Assistant)","Clear Night","Sunny / Clear Day","Partly Cloudy (Day)","Partly Cloudy (Night)","Cloudy / Overcast (Day)","Cloudy / Overcast (Night)","Fog / Mist (Day)","Fog / Mist (Night)","Rainy (Day)","Rainy (Night)","Pouring / Heavy Rain","Snow (Day)","Snow (Night)","Thunderstorm (Day)","Thunderstorm (Night)","Windy"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"home_clock_tap_action",label:"Home Time Tap",domain:"select",default:"Time App",section:"interface",group_tier:"interface",options:["Time App","Clock Face"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"home_date_tap_action",label:"Home Date Tap",domain:"select",default:"Overview",section:"interface",group_tier:"interface",options:["Day View","Overview"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"local_clock_label",label:"Local Clock Label",domain:"text",default:"",section:"time",group_tier:null,options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"show_utc_clock",label:"Show UTC Clock",domain:"switch",default:!1,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"world_clocks",label:"World Clocks",domain:"text",default:"",section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"alarms_summary",label:"Alarms",domain:"text",default:"07:00|0|1;08:30|0|2;09:00|0|2",section:"time",group_tier:null,options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"calendar_lookahead_days",label:"Overview Lookahead",domain:"number",default:30,section:"interface",group_tier:"interface",options:[],min:7,max:60,step:1,unit:"d",capability:"display"},{key:"calendar_week_start",label:"Start Week On",domain:"select",default:"Sunday",section:"interface",group_tier:"interface",options:["Sunday","Monday"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"bedtime_active",label:"Bedtime Mode",domain:"switch",default:!1,section:"power",group_tier:null,options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"bedtime_display",label:"Idle Display in Bedtime",domain:"select",default:"Screen Off",section:"power",group_tier:"behavior",options:["Screen Off","Ambient Clock"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"bedtime_schedule",label:"Bedtime Schedule",domain:"switch",default:!1,section:"power",group_tier:"behavior",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"bedtime_start_hour",label:"Bedtime Starts",domain:"number",default:22,section:"power",group_tier:"behavior",options:[],min:0,max:23,step:1,unit:":00",capability:"display"},{key:"bedtime_end_hour",label:"Bedtime Ends",domain:"number",default:7,section:"power",group_tier:"behavior",options:[],min:0,max:23,step:1,unit:":00",capability:"display"},{key:"bedtime_brightness",label:"Bedtime Brightness",domain:"number",default:15,section:"power",group_tier:"behavior",options:[],min:1,max:100,step:1,unit:"%",capability:"display"},{key:"camera_default_view",label:"Default camera view",domain:"select",default:"Grid",section:"interface",group_tier:"interface",options:["Grid","Single","Carousel"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"camera_carousel_interval",label:"Carousel interval",domain:"select",default:"15s",section:"interface",group_tier:"interface",options:["10s","15s","30s","60s"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"camera_framing",label:"Camera framing",domain:"select",default:"Uncropped",section:"interface",group_tier:"interface",options:["Uncropped","Fill"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"camera_stream_mode",label:"Camera stream mode",domain:"select",default:"Auto",section:"interface",group_tier:"interface",options:["Auto","Low Bandwidth","Snapshots"],min:null,max:null,step:null,unit:"",capability:"display"},{key:"camera_doorbell_popup",label:"Doorbell ring popup",domain:"select",default:"Snapshot",section:"interface",group_tier:"interface",options:["Snapshot","Live Video"],min:null,max:null,step:null,unit:"",capability:"hw_jpeg"},{key:"screensaver_photo_clock",label:"Show subtle clock",domain:"switch",default:!1,section:"display",group_tier:"display",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"weather_app_background",label:"Weather app background",domain:"switch",default:!0,section:"interface",group_tier:"interface",options:[],min:null,max:null,step:null,unit:"",capability:"display"},{key:"do_not_disturb",label:"Do not disturb",domain:"switch",default:!1,section:"power",group_tier:null,options:[],min:null,max:null,step:null,unit:"",capability:"display"}],pt=Object.fromEntries(jn.map(e=>[e.key,e]));var fo=["app:pinned","app:music","app:home_hub","app:cameras","app:area","app:remote","app:games","app:tools"];var pa="calendar,music_queue,stopwatch,alarms,timers",ma=["calendar","music_queue","stopwatch","alarms","timers"],ga="scene,light,cover,fan,switch,climate,media",_a=["scene","light","cover","fan","switch","climate","media"],ha="alarm,intercom,thermostat,entry,vacuum",va=["alarm","intercom","thermostat","entry","vacuum"],ba="stopwatch,level,flashlight,calculator,dice,coin_flip",fa=["stopwatch","level","flashlight","calculator","dice","coin_flip"],ya="marbles,archery,bricks,chomp,2048,memory",wa=["marbles","archery","bricks","chomp","2048","memory"];var at=24,yo=96,wo=24,Ue=["app:pinned","app:music","app:home_hub","app:cameras","app:area","app:remote","app:weather","app:time","app:calendar","app:clock","app:tools","app:games"],Sa={"app:pinned":"pinned","app:music":"music","app:home_hub":"home_hub","app:cameras":"cameras","app:area":"area","app:remote":"remote","app:weather":"weather","app:time":"time","app:calendar":"calendar","app:clock":"clock","app:tools":"tools","app:games":"games"},Yn={Pinned:"pinned",Media:"music","Home Hub":"home_hub",Cameras:"cameras","Area Controls":"area",Remote:"remote",Weather:"weather","Time App":"time",Calendar:"calendar","Clock Face":"clock",Tools:"tools",Games:"games"},ii=15*1024*1024,So=36,de="__all__",Ye="__defaults__",Ze="__uploads__",mt="__uncategorized__",qt={dashboard:"overview",display:"display",interface:"interface",audio_voice:"audio",power:"power",presence:"presence",tools:"tools"},Gt={system_overview:"overview",shared_entities:"shared",photos:"photos",remotes:"remotes",system_sync:"groups",area_tracking:"presence",system_tools:"tools"},Zn=pt.start_screen?.options??[],Xn=pt.home_clock_tap_action?.options??[],Jn=pt.home_date_tap_action?.options??[];var Qn=pt.calendar_week_start?.options??[],ko=4,ai="07:00|0|1;08:30|0|2;09:00|0|2",es=pt.return_to_home_timeout?.options??[];var ts=new Set(["pocket_carry","handhelds","wearables","wall_panels"]),os=["native_ble_tracking","ble_auto_switch","sync_device_area","area_follow_dwell_s","area_handoff","security_pin_policy"],is=["wallpaper_mode","wallpaper_source","wallpaper_collection","wallpaper_favorites","wallpaper_cycle_minutes","screensaver_photo_mode","screensaver_photo_source","screensaver_photo_collection","screensaver_photo_ids","screensaver_cycle_minutes","screensaver_shuffle","device_custom_color"],as=["dock_items","pinned_items","area_categories","home_categories","tools_items","games_items","activity_card","activity_sources","device_remote_group","camera_visible_entities","camera_carousel_entities"],ka={ble:"BLE",cpu:"CPU",db:"dB",dbm:"dBm",dns:"DNS",esp:"ESP",esphome:"ESPHome",ha:"HA",http:"HTTP",id:"ID",imu:"IMU",ip:"IP",ips:"IPS",led:"LED",ma:"MA",mac:"MAC",mic:"Mic",mjpeg:"MJPEG",ota:"OTA",pin:"PIN",pmu:"PMU",psram:"PSRAM",ram:"RAM",rgb:"RGB",rssi:"RSSI",rtsp:"RTSP",sdk:"SDK",sram:"SRAM",ssid:"SSID",tts:"TTS",ui:"UI",url:"URL",usb:"USB",uuid:"UUID",va:"VA",wifi:"Wi-Fi","wi-fi":"Wi-Fi"};var $a={"shell.title":"Latter","shell.toggle_ha_sidebar":"Toggle the Home Assistant sidebar","shell.install_update":"Install update","shell.rev_updated_banner":"Latter Studio was updated \u2014 reload page","shell.reload_page":"Reload page","shell.loading":"Loading Latter\u2026","shell.loading_device":"Loading Device\u2026","shell.retry":"Retry","shell.saved_status":"Saved","shell.dismiss_toast":"Dismiss notification","nav.scope_label":"Scope","nav.devices":"Devices","nav.system":"System","nav.managed":"Managed","nav.discovered":"Discovered","nav.back_managed":"\u2190 Managed","nav.device_pages_label":"Device pages","nav.system_pages_label":"System pages","nav.devices_list_label":"Devices","view.system_overview":"Overview","view.shared_entities":"Shared entities","view.photos":"Photos","view.remotes":"Media & remotes","view.system_sync":"Device groups","view.area_tracking":"BLE & Area presence","view.system_tools":"Tools","view.select_device_prompt":"Managed devices","view.discovered_devices":"Discovered devices","view.dashboard":"Overview","view.display":"Display","view.interface":"Interface","view.audio_voice":"Audio","view.power":"Power","view.presence":"Presence","view.tools":"Tools","action.cancel":"Cancel","action.confirm":"Confirm","action.done":"Done","action.close":"Close","action.save":"Save","action.reset":"Reset","action.edit":"Edit","action.delete":"Delete","action.add":"Add","action.adopt":"Adopt","action.ignore":"Ignore","action.unignore":"Restore","action.configure":"Configure","action.run":"Run","action.install":"Install","action.refresh":"Refresh","action.dismiss":"Dismiss","action.open_in_ha":"Open in Home Assistant","action.open_integration":"Open integration","action.open_repairs":"Open Repairs","action.open_ha_logs":"Open Home Assistant logs","action.open_shared_entities":"Open shared entities","action.download_backup":"Download backup","action.download_backup_first":"Download backup first","action.restore_backup":"Restore backup","action.download_diagnostics":"Download diagnostics","action.add_custom_shortcut":"Add custom shortcut","action.add_pinned_item":"Add pinned item","action.reset_default_dock":"Reset default dock","action.save_custom_group":"Save custom group","action.save_group":"Save group","action.save_shortcut":"Save shortcut","action.save_color":"Save color","action.add_ble_tag":"Add BLE tag","action.manage_groups":"Manage groups","action.default_icon":"Default icon","action.move_up":"Move {item} up","action.move_down":"Move {item} down","action.move_earlier":"Move {item} earlier","action.move_later":"Move {item} later","action.drag_reorder":"Drag to reorder {item}","action.remove_item":"Remove {item}","action.edit_item":"Edit {item}","action.configure_item":"Configure {item}","common.none_option":"\u2014 None \u2014","common.none_configured":"None configured","common.unassigned":"Unassigned","common.no_person":"No person","common.custom":"Custom","common.auto":"Auto","common.active":"Active","common.enabled":"Enabled","common.disabled":"Disabled","common.all_off":"All off","common.loading":"Loading\u2026","common.unknown":"\u2014","common.missing_suffix":"{id} (missing)","common.reordered_status":"Moved {item} to position {position} of {total}","common.keep_one_enabled":"Keep at least one {noun} enabled","status.online":"Online","status.offline":"Offline","status.update":"Update available","status.up_to_date":"Up to date","status.away":"Away","status.scanning":"Scanning","status.sleeping":"Sleeping","status.charging":"Charging","status.plugged_in":"Plugged in","status.on_battery":"On battery","status.always_on":"Always on","status.sleep_wake_active":"Sleep & wake active","status.stationary":"Stationary","status.roaming":"Roaming","status.phone":"Phone","status.ble_tag":"BLE tag","status.needs_attention":"Needs attention","status.pin_configured":"PIN configured","status.pin_not_set":"Not set","signal.no_reading":"No reading","signal.excellent":"Excellent","signal.good":"Good","signal.fair":"Fair","signal.weak":"Weak","combobox.placeholder":"Search name, Area, or entity ID\u2026","combobox.no_matches":"No matching entities","combobox.clear":"Clear selection","combobox.showing_top":"Showing top {shown} of {total} matches","sync.conflict_reloaded":"Settings changed in another session; refreshed latest state.","sync.restarting_device":"Restarting Device\u2026","sync.hibernating_device":"Hibernating Device\u2026","sync.triggered_action":'Triggered "{label}"',"sync.device_not_found":"Requested Device was not found; showing Managed devices.","sync.save_device_failed":"Could not save Device settings","sync.save_device_named_failed":'Could not save settings for "{title}": {error}',"sync.save_system_failed":"Could not save System settings","issue.link_ma_player":"Not linked to its Music Assistant player.","issue.missing_mapped_entity":"A chosen entity no longer exists.","issue.missing_mapped_entity_detail":"A chosen entity no longer exists: {detail}.","issue.ble_no_proxies":"BLE Area tracking is on, but no Bluetooth proxy is assigned to an Area.","issue.slot_push_failing":"Latter cannot send Area and browse pages to this Device.","issue.device_crashed":"Restarted after a crash.","issue.device_crashed_detail":"Restarted after a crash ({detail}).","issue.device_crashed_stall":"Restarted itself after its main loop stalled for 30 seconds.","issue.device_brownout":"Restarted after a power dip (brownout).","issue.firmware_rolled_back":"A firmware update failed to start; the previous firmware is running.","issue.generic":"Repair: {label}.","card.perimeter_security":"Perimeter security","card.perimeter_security_signing":"Perimeter security & signing","card.notifications_announcements":"Notifications & announcements","card.doorbell_intercom_audio":"Doorbell & intercom audio","card.backup_restore":"Backup & restore","card.system_device_logs":"System & Device logs","card.support_diagnostics":"Support & diagnostics","card.support_subtitle":"Version lockstep, redacted System diagnostics bundle, and issue reporting.","card.area_deployment":"Area deployment","card.home_hub_weather":"Home hub & weather","card.calendars":"Calendars","card.cameras_doorbell":"Cameras & doorbell audio","card.custom_colors":"Custom colors","card.photo_library":"Photo library","card.remote_controls":"Remote controls","card.volume_overrides":"Speaker volume overrides","card.remote_groups":"Remote control groups","card.area_presence_sensors":"Area presence & sensors","card.ble_calibration":"Walk-around BLE calibration","card.advanced_ble":"Advanced BLE settings","support.ha_version":"Home Assistant","support.integration_version":"Latter integration","support.sdk_rev":"Minimum firmware SDK","support.studio_rev":"Studio contract","support.managed_devices":"Managed Devices","support.managed_devices_value":"{total} ({displays} displays, {trackers} BLE trackers)","support.copy_summary":"Copy version summary","support.copied_summary":"Copied version summary to clipboard","support.download_system_diagnostics":"Download System diagnostics","support.documentation":"Documentation","support.report_issue":"Report an issue","sys_overview.no_devices":"No Devices","sys_overview.issues_one":"1 issue","sys_overview.issues_many":"{count} issues","sys_overview.updates_one":"1 update","sys_overview.updates_many":"{count} updates","sys_overview.all_online":"All online","sys_overview.healthy":"Healthy","sys_overview.sleeping_count":"{count} sleeping","sys_overview.away_count":"{count} away","sys_overview.scanning_count":"{count} scanning","sys_overview.offline_count":"{count} offline","sys_overview.low_battery_count":"{count} low battery","sys_overview.online_ratio":"{online} / {total} online","sys_overview.zero_devices":"0 Devices","sys_overview.ready_to_onboard":"Ready to onboard","sys_overview.displays_one":"1 display","sys_overview.displays_many":"{count} displays","sys_overview.phones_one":"1 phone","sys_overview.phones_many":"{count} phones","sys_overview.ble_tags_one":"1 BLE tag","sys_overview.ble_tags_many":"{count} BLE tags","sys_overview.audio_count":"{count} audio","sys_overview.open_device":"Open Device","sys_overview.discovered_banner_title":"Hardware ready to adopt","sys_overview.discovered_banner_one":"1 unbound Latter Device detected on your network ({names}).","sys_overview.discovered_banner_many":"{count} unbound Latter Devices detected on your network ({names}).","sys_overview.open_discovered":"Open discovered","sys_overview.tile_devices":"Managed Devices","sys_overview.tile_areas":"Area presence","sys_overview.occupied_count":"{count} occupied","sys_overview.areas_proxies_meta":"{areas} \u2022 {proxies}","sys_overview.areas_one":"1 Area","sys_overview.areas_many":"{count} Areas","sys_overview.proxies_one":"1 BLE proxy","sys_overview.proxies_many":"{count} BLE proxies","sys_overview.no_areas":"No Areas configured","sys_overview.tile_people_roaming":"People & roaming","sys_overview.people_assigned_one":"1 person assigned","sys_overview.people_assigned_many":"{count} people assigned","sys_overview.ble_tracked_meta":"{count} BLE-tracked","sys_overview.tile_release":"System release","sys_overview.fw_updates_one":"1 firmware update available","sys_overview.fw_updates_many":"{count} firmware updates available","sys_overview.check_fw_updates":"Check firmware updates","sys_overview.area_deployment_subtitle":"Live occupancy, assigned Devices, and Bluetooth coverage across your Areas.","sys_overview.manage_presence":"Manage presence","sys_overview.roaming_devices":"Roaming Devices","sys_overview.roaming_active_ratio":"{online} / {total} active","sys_overview.plus_more":"+{count} more","sys_overview.here_prefix":"Here: {names}","sys_overview.remotes_one":"1 remote","sys_overview.remotes_many":"{count} remotes","sys_overview.active_sensors_one":"1 active sensor","sys_overview.active_sensors_many":"{count} active sensors","sys_overview.sensors_one":"1 sensor","sys_overview.sensors_many":"{count} sensors","sys_overview.occupied":"Occupied","sys_overview.no_devices_stationed":"No Devices stationed","sys_overview.signature_count":"Signature ({count})","sys_overview.ble_proxy":"BLE proxy","sys_overview.no_ble_proxy":"No BLE proxy","sys_overview.empty_deployment":"No Home Assistant Areas or managed Devices configured yet.","sys_overview.unconfigured_areas_one":"+1 additional Home Assistant Area without Latter Devices or BLE coverage.","sys_overview.unconfigured_areas_many":"+{count} additional Home Assistant Areas without Latter Devices or BLE coverage.","sys_overview.photos_count_one":"1 photo","sys_overview.photos_count_many":"{count} photos","shared.home_hub_subtitle":"Shared climate zones, entry controls, vacuums, security, and weather across every Device.","shared.weather_label":"Weather","shared.security_alarm_label":"Security alarm","shared.thermostat_zones":"Thermostat zones","shared.add_zone":"Add zone","shared.choose_thermostat":"\u2014 Choose a thermostat \u2014","shared.thermostat_aria":"Thermostat zone","shared.remove_thermostat":"Remove thermostat zone","shared.door_locks":"Door locks","shared.add_lock":"Add lock","shared.choose_lock":"\u2014 Choose a door lock \u2014","shared.lock_aria":"Door lock","shared.remove_lock":"Remove door lock","shared.garage_doors":"Garage doors","shared.add_garage":"Add garage door","shared.choose_garage":"\u2014 Choose a garage door \u2014","shared.garage_aria":"Garage door","shared.remove_garage":"Remove garage door","shared.robot_vacuums":"Robot vacuums","shared.add_vacuum":"Add vacuum","shared.choose_vacuum":"\u2014 Choose a robot vacuum \u2014","shared.vacuum_aria":"Robot vacuum","shared.remove_vacuum":"Remove robot vacuum","shared.broadcast_speakers":"Broadcast speakers","shared.add_speaker":"Add speaker","shared.choose_speaker":"\u2014 Choose a speaker \u2014","shared.speaker_aria":"Broadcast speaker","shared.remove_speaker":"Remove broadcast speaker","shared.broadcast_phrases":"Quick broadcast phrases","shared.add_phrase":"Add phrase","shared.phrase_placeholder":"Enter a quick broadcast phrase\u2026","shared.phrase_aria":"Quick broadcast phrase","shared.remove_phrase":"Remove quick broadcast phrase","shared.calendars_subtitle":"Upcoming events merged into the Activity card and agenda feed.","shared.add_calendar":"Add calendar","shared.choose_calendar":"\u2014 Choose a calendar \u2014","shared.empty_calendars":"No calendars configured yet.","shared.calendar_aria":"Calendar","shared.remove_calendar":"Remove calendar","shared.cameras_subtitle":"Up to 10 cameras. Doorbell ring sensors wake displays automatically with listen audio and push-to-talk TTS replies.","shared.add_camera":"Add camera","shared.doorbell_filter_label":"Doorbell audio filter","shared.doorbell_filter_desc":"Noise-reduction preset applied when listening to camera audio.","shared.filter_strong":"Strong","shared.filter_light":"Light","shared.filter_off":"Off","shared.choose_camera":"\u2014 Choose a camera \u2014","shared.empty_cameras":"No cameras configured yet.","shared.camera_aria":"Camera","shared.remove_camera":"Remove camera","shared.camera_slot_primary":"Camera 1 (primary)","shared.camera_slot_n":"Camera {index}","shared.preview":"Preview","shared.preview_heading":"Preview: {entity}","shared.camera_preview_alt":"Camera preview","shared.cam_cap_rtsp":"RTSP","shared.cam_cap_mjpeg":"MJPEG","shared.cam_cap_snapshot":"Snapshot","shared.cam_cap_doorbell":"Doorbell","shared.cam_cap_label":"Label: {label}","shared.cam_cap_listen":"Listen","shared.cam_cap_talk":"Talk","shared.cam_cap_reply":"Reply","shared.cam_cap_unlock":"Unlock: {entity}","shared.cam_cfg_title":"Camera options","shared.cam_cfg_label":"Display label","shared.cam_cfg_label_desc":"Short name shown on Latter displays (leave blank to use Home Assistant's name).","shared.cam_cfg_listen":"Show Listen button","shared.cam_cfg_listen_desc":"Allow monitoring camera audio from the camera view and doorbell popup.","shared.cam_cfg_talk":"Show Talk button","shared.cam_cfg_talk_desc":"Allow push-to-talk voice replies through this camera's speaker.","shared.cam_cfg_talk_no_speaker_desc":"No paired speaker was auto-detected for this camera, but you can still enable Talk manually.","shared.cam_cfg_reply":"Show Quick Reply button","shared.cam_cfg_reply_desc":"Show quick spoken reply presets on the camera view and doorbell popup.","shared.cam_cfg_unlock":"Unlock / Open button","shared.cam_cfg_unlock_desc":"Optionally link a specific door lock or garage door to show an Unlock/Open button on this camera.","shared.cam_cfg_unlock_none":"None (hide button)","shared.colors_subtitle":"Shared 24-swatch accent library available across all Devices.","shared.add_color":"Add color","shared.delete_color_aria":"Delete color {name}","shared.empty_colors":"No custom colors saved yet.","remotes.controls_subtitle":"Up to 10 TV, streamer, or receiver entities controlled from the Remote screen.","remotes.add_remote":"Add remote","remotes.choose_remote":"\u2014 Choose a remote or media player \u2014","remotes.empty_remotes":"No remote controls configured yet.","remotes.remote_aria":"Remote or media player","remotes.remove_remote":"Remove remote","remotes.slot_primary":"Slot 1 (primary power target)","remotes.slot_n":"Slot {index}","remotes.overrides_subtitle":"Redirects volume buttons when audio plays through an external AVR or soundbar.","remotes.add_override":"Add override","remotes.when_playing_on":"When audio plays on","remotes.speaker_aria":"Speaker","remotes.choose_speaker":"\u2014 Choose a speaker \u2014","remotes.change_volume_on":"Change the volume on","remotes.volume_target_aria":"Volume target","remotes.choose_volume_target":"\u2014 Choose a volume target \u2014","remotes.remove_override_aria":"Remove volume override","remotes.empty_overrides":"No volume overrides configured.","remotes.groups_subtitle":"Bind sets of remotes to Home Assistant Areas or specific Devices.","remotes.add_group":"Add group","remotes.group_name":"Group name","remotes.group_name_placeholder":"e.g. Living Area TV","remotes.loads_in_area":"Loads in Area","remotes.area_aria":"Area","remotes.no_area_option":"No Area (assign to Devices only)","remotes.delete_group_aria":"Delete remote group {name}","remotes.group_remotes_label":"Remote controls","remotes.primary_badge":"\u2605 Primary: {name}","remotes.numbered_badge":"#{index}: {name}","remotes.add_badge":"+ {name}","remotes.add_remotes_first":"Add remote controls first.","remotes.empty_groups":"No remote groups yet.","groups.card_title":"Group presets & custom groups","groups.card_subtitle":"Built-in hardware presets and custom Device groups that keep assigned Devices aligned.","groups.create_group":"Create group","groups.group_name":"Group name","groups.group_name_placeholder":"e.g. Guest suites","groups.description_optional":"Description (optional)","groups.description_placeholder":"Optional description","groups.copy_from_aria":"Copy settings from Device","groups.start_from_defaults":"Start from default settings","groups.copy_from_prefix":"Copy from: {title}","groups.members_one":"1 Device","groups.members_many":"{count} Devices","groups.scope_display_chip":"Display","groups.scope_interface_chip":"Interface","groups.view_devices":"View Devices","groups.reset_preset":"Reset preset","groups.reset_preset_toast":'Reset "{name}" to preset defaults',"groups.delete_group_aria":"Delete group {name}","groups.devices_list_meta":"Devices: {names}","groups.no_devices_assigned":"No Devices assigned","groups.empty_groups":"No Device groups configured.","groups.custom_summary_title":"Custom (individual settings)","groups.custom_summary_desc":"Devices move to Custom automatically when individual settings diverge from a group baseline.","groups.detached_toast":'Detached "{title}" to Custom (individual settings)',"groups.detached_many_toast":"Applied changes ({count} Devices switched to Custom)","groups.baseline_settings":"Baseline settings","groups.section_power_brightness":"Power & brightness","groups.section_audio_voice":"Audio & voice","groups.section_presence_security":"Presence & security","groups.section_display":"Display","groups.section_interface":"Interface & shortcuts","groups.for_group_aria":"{label} for {group}","groups.remote_match_area":"Follow the active Area","groups.remote_group_prefix":"Group: {name}","groups.remote_all_system":"All System remotes","groups.dock_baseline_desc_one":"Baseline holds 1 shortcut (captures from source Device below).","groups.dock_baseline_desc_many":"Baseline holds {count} shortcuts (captures from source Device below).","groups.copy_dock":"Copy dock","groups.pinned_baseline_desc_one":"Baseline holds 1 shortcut (captures from source Device below).","groups.pinned_baseline_desc_many":"Baseline holds {count} shortcuts (captures from source Device below).","groups.copy_pinned":"Copy pinned","groups.clocks_baseline_desc_one":"Baseline holds 1 zone (captures from source Device below).","groups.clocks_baseline_desc_many":"Baseline holds {count} zones (captures from source Device below).","groups.copy_clocks":"Copy clocks","groups.copy_from_device":"Copy from Device","groups.source_device":"Source Device","groups.source_device_desc":"Replaces this group's active baseline scope with an existing Device's settings.","groups.copy_into_aria":"Copy settings into {name}","groups.copy_settings":"Copy settings","groups.confirm_copy_title":'Copy settings into "{group}"?',"groups.confirm_copy_body":'Updates the "{group}" baseline from "{device}" and syncs all assigned Devices.',"groups.confirm_copy_list_body":'Copies {listLabel} from "{device}" into the "{group}" baseline and syncs assigned Devices.',"groups.confirm_copy_confirm":"Copy into baseline","groups.include_display":"Include display settings","groups.include_display_desc":"Sync wallpapers, clock face, color profile, and media appearance.","groups.include_interface":"Include interface & shortcuts","groups.include_interface_desc":"Sync start screen, App Dock, pinned shortcuts, and hub categories.","batch.title":"Batch controls","batch.subtitle":"Stage changes across a filtered set of Devices, then apply them together without altering saved group baselines.","batch.target_filter_aria":"Target Devices for batch controls","batch.category_filter_aria":"Filter batch controls by category","batch.all_latter_devices":"All Latter Devices","batch.online_devices":"Online Devices","batch.roaming_devices":"Roaming Devices","batch.stationary_devices":"Stationary Devices","batch.all_categories":"All categories","batch.cat_display":"Display","batch.cat_interface":"Interface","batch.cat_audio":"Audio","batch.cat_power":"Power","batch.cat_presence":"Presence","batch.cat_security":"Security","batch.staged_count":"{count} staged","batch.staged_badge":"Staged","batch.mixed_badge":"Mixed","batch.mixed_pill_suffix":"{label} (mixed)","batch.mixed_hint":"Target Devices currently have different values \u2014 choose a value to stage across all targets.","batch.row_meta_one":"{section} \u2022 1 Device","batch.row_meta_many":"{section} \u2022 {count} Devices","batch.detachment_note_one":"1 grouped Device will switch to Custom if staged settings diverge from its group baseline.","batch.detachment_note_many":"{count} grouped Devices will switch to Custom if staged settings diverge from their group baselines.","batch.apply_to_n":"Apply to {count} Devices","batch.apply_to_one":"Apply to 1 Device","batch.applied_to_n":"Applied staged changes to {count} Devices","batch.applied_to_one":"Applied staged changes to 1 Device","batch.reset_staged":"Reset","batch.no_targets":"No Devices match the selected filter.","batch.empty_all":"No Latter Devices onboarded yet.","batch.empty_target":"No Latter Devices currently match {target}.","batch.empty_category":"No batch controls match this category.","batch.target_summary":"Target ({count}): {names}","batch.copy_lists_title":"Copy multi-item lists","batch.template_device":"Template Device","batch.template_device_aria":"Template Device for batch list copy","batch.template_device_desc":"Copies App Dock, pinned shortcuts, or world clocks to {target}.","batch.push_dock":"Push App Dock","batch.push_pinned":"Push pinned shortcuts","batch.push_clocks":"Push world clocks","batch.confirm_push_list_title":"Push {listLabel} to {target}?","batch.confirm_push_list_body":'Replaces {listLabel} on matching Devices using "{device}" as the template.',"batch.confirm_push_list_confirm":"Push list","presence_sys.area_card_subtitle":"Configures how each Area combines Bluetooth tracking and occupancy sensors.","presence_sys.mode_weighted":"Weighted (BLE and sensors)","presence_sys.mode_any_or":"Either (BLE or a sensor)","presence_sys.mode_ble_only":"BLE only","presence_sys.mode_both":"Both (BLE and a sensor)","presence_sys.occupied_sensor":"Occupied (sensor)","presence_sys.empty":"Empty","presence_sys.ble_dbm":"BLE {rssi} dBm{distance}","presence_sys.signature_match":"signature match","presence_sys.active_sensors_one":"1 active sensor","presence_sys.active_sensors_many":"{count} active sensors","presence_sys.clear_sensors_one":"1 sensor clear","presence_sys.clear_sensors_many":"{count} sensors clear","presence_sys.unavailable_sensors_one":"1 sensor unavailable","presence_sys.unavailable_sensors_many":"{count} sensors unavailable","presence_sys.calibrated_meta":"calibrated {when} ({samples} samples)","presence_sys.calibrate_hint":"calibrate with a carried Device to detect BLE presence here","presence_sys.clear_signature":"Clear signature","presence_sys.calibrate":"Calibrate","presence_sys.occupied_chip":"Occupied \u2022 {confidence}","presence_sys.clear_chip":"Clear","presence_sys.signature_proxies_one":"Signature (1 proxy)","presence_sys.signature_proxies_many":"Signature ({count} proxies)","presence_sys.presence_mode":"Presence mode","presence_sys.presence_mode_aria":"Presence mode for {area}","presence_sys.sensor_threshold_drawer":"Sensor & threshold settings","presence_sys.occupied_at":"Occupied at","presence_sys.occupied_at_weighted_desc":"The Area counts as occupied when the combined BLE and sensor score reaches this level.","presence_sys.occupied_at_other_desc":"Used only in Weighted mode.","presence_sys.sensors_that_count":"Sensors that count","presence_sys.sensors_selected_desc":"{selected} of {total} selected.","presence_sys.sensors_all_desc":"None selected: every sensor in this Area counts.","presence_sys.sensors_group_aria":"Sensors that count in {area}","presence_sys.calibrate_all_lux":"Auto-calibrate lux","presence_sys.lux_chip":"{lux} lx ({level}%)","presence_sys.ambient_sensor":"Ambient light sensor","presence_sys.ambient_sensor_aria":"Ambient light sensor for {area}","presence_sys.ambient_sensor_auto":"Auto ({sensor})","presence_sys.ambient_sensor_auto_none":"Auto (none detected)","presence_sys.ambient_sensor_disabled":"None (use schedule fallback)","presence_sys.ambient_dark_lux":"Dark floor (lx)","presence_sys.ambient_bright_lux":"Bright ceiling (lx)","presence_sys.ambient_calibration_desc":"Auto-calibrate from 7-day Home Assistant statistics or tune manually for this sensor.","presence_sys.calibrate_lux_btn":"Auto-calibrate","presence_sys.calibrating_lux":"Calibrating\u2026","presence_sys.lux_bounds_error":"Dark floor must be lower than bright ceiling.","presence_sys.calibrate_lux_done":"Calibrated ambient light for {count} Areas.","presence_sys.calibrate_lux_one_done":"Calibrated {area}: {dark}\u2013{bright} lx.","presence_sys.no_area_sensors":"This Area has no occupancy, motion, or door sensors.","presence_sys.empty_areas":"No Home Assistant Areas, Bluetooth proxies, or occupancy sensors found yet.","presence_sys.calibration_subtitle":"Carry a tracked Device into an Area to check Bluetooth proxy signal levels or save an Area signature.","presence_sys.pause_stream":"Pause stream","presence_sys.resume_stream":"Resume stream","presence_sys.open_discovered":"Open discovered Devices","presence_sys.empty_ble_devices":"No Devices currently have Bluetooth Area tracking enabled. Turn on BLE Area tracking on a portable Device, or adopt a phone or tag under Discovered devices.","presence_sys.handoff_ready":"Ready to calibrate {area} \u2014 carry {device} into {area} and select Calibrate Area.","presence_sys.your_device":"your Device","presence_sys.this_device":"this Device","presence_sys.this_area":"this Area","presence_sys.carried_device":"Carried Device","presence_sys.carried_device_desc":"Choose the actively tracked Device or BLE tag you are holding.","presence_sys.live_signal_active":"Live BLE signal active \u2014 currently detected in ","presence_sys.packets_observed":" ({count} packets observed).","presence_sys.no_recent_packets_prefix":"No live BLE packets in the last 12 seconds \u2014 wake ","presence_sys.no_recent_packets_suffix":" or hold it in hand so its Bluetooth beacon broadcasts before calibrating.","presence_sys.standing_in_area":"Standing in Area","presence_sys.cal_desc_no_areas":"Create at least one Home Assistant Area before saving a Bluetooth signature.","presence_sys.cal_desc_replace":"Updates the saved {count}-proxy Bluetooth signature for {area} using live signal readings.","presence_sys.cal_desc_proxyless":"Saves readings from nearby Bluetooth proxies so {area} can detect presence even without its own proxy.","presence_sys.cal_desc_new":"Saves Bluetooth signal strengths from nearby proxies while you stand in {area} for more accurate Area boundaries.","presence_sys.suffix_saved":" (signature saved)","presence_sys.suffix_no_proxy":" (no BLE proxy)","presence_sys.no_ha_areas_option":"No Home Assistant Areas configured","presence_sys.calibrate_area_btn":"Calibrate Area","presence_sys.nearby_proxies":"Nearby Bluetooth proxies","presence_sys.unassigned_proxy":"Unassigned proxy","presence_sys.assign_area_in_ha":"Assign Area in Home Assistant","presence_sys.active_winner":"Active winner","presence_sys.stale_suffix":" (stale)","presence_sys.trim_suffix":" \u2022 trim {offset}","presence_sys.antenna_trim":"Antenna trim","presence_sys.antenna_trim_help":"Raw {raw} \u2022 Offset {offset} \u2014 adjust only if this proxy consistently reads stronger or weaker across every Area.","presence_sys.minus_one_db":"-1 dB","presence_sys.plus_one_db":"+1 dB","presence_sys.empty_survey":"No Bluetooth proxy readings yet for this Device.","presence_sys.advanced_subtitle":"System-wide away timeout, maximum detection distance, movement smoothing, and wall signal drop-off.","presence_sys.away_timeout":"Away timeout","presence_sys.away_timeout_desc":"Seconds without any Bluetooth packet before a tracked tag or offline Device is marked Away.","presence_sys.max_radius":"Maximum Area radius","presence_sys.max_radius_desc":"Ignores Bluetooth proxies farther than this distance in meters so outdoor signals do not claim indoor Areas.","presence_sys.max_radius_ft":"Maximum Area radius (ft)","presence_sys.max_radius_ft_desc":"Ignores Bluetooth proxies farther than this distance in feet so outdoor signals do not claim indoor Areas.","presence_sys.max_speed":"Maximum movement speed","presence_sys.max_speed_desc":"Smooths sudden signal drops that would imply movement faster than this speed in meters per second.","presence_sys.max_speed_fps":"Maximum movement speed (ft/s)","presence_sys.max_speed_fps_desc":"Smooths sudden signal drops that would imply movement faster than this speed in feet per second.","presence_sys.attenuation":"Wall signal drop-off","presence_sys.attenuation_desc":"Controls how quickly Bluetooth signal strength fades with distance through walls (default 2.2).","tools_sys.announce_subtitle":"Send screen popups or spoken intercom broadcasts to all Devices, occupied Areas, or one display.","tools_sys.announce_mode_aria":"Announcement mode","tools_sys.screen_notification":"Screen notification","tools_sys.voice_broadcast":"Voice broadcast","tools_sys.target_label":"Target","tools_sys.all_displays":"All Latter displays","tools_sys.occupied_areas_only":"Occupied Areas only","tools_sys.device_prefix":"Device: {title}","tools_sys.notification_title":"Notification title","tools_sys.notification_title_placeholder":"e.g. Front gate","tools_sys.priority":"Priority","tools_sys.priority_normal":"Normal","tools_sys.priority_warning":"Warning","tools_sys.priority_critical":"Critical","tools_sys.include_camera":"Include primary camera","tools_sys.message":"Message","tools_sys.message_placeholder":"Message to display or speak\u2026","tools_sys.send_now":"Send now","tools_sys.doorbell_subtitle":"Verify push-to-talk TTS reply playback through Camera 1's bound door speaker.","tools_sys.source_device":"Source Device","tools_sys.source_device_desc":"Latter Device context used when routing the door speaker reply.","tools_sys.no_latter_devices":"\u2014 No Latter Devices \u2014","tools_sys.test_door_reply":"Test door speaker reply","tools_sys.doorbell_desc_no_cam":"Add a camera with a bound door speaker in Shared entities first to test TTS reply playback.","tools_sys.doorbell_desc_no_dev":"Onboard at least one Latter Device first to route push-to-talk test replies.","tools_sys.doorbell_desc_ready":"Plays a short TTS phrase on Camera 1's bound media player ({camera}).","tools_sys.doorbell_reply_placeholder":"Testing Latter doorbell audio.","tools_sys.play_door_speaker":"Play on door speaker","tools_sys.logs_filter_aria":"Filter diagnostic logs","tools_sys.logs_all":"All events","tools_sys.logs_studio":"Latter Studio","tools_sys.logs_errors":"Warnings & errors","tools_sys.refresh_logs":"Refresh logs","tools_sys.copy_logs":"Copy logs","tools_sys.clear_logs":"Clear logs","tools_sys.backup_subtitle":"Export or restore non-secret System and Device settings as portable JSON bundles.","tools_sys.export_scope":"Export scope","tools_sys.entire_system":"Entire System + all Devices","tools_sys.restore_from_backup":"Restore from backup","tools_sys.target_device_restore":"Target Device (for single-Device backups)","tools_sys.auto_system_backup":"\u2014 Automatic (System backup) \u2014","tools_sys.system_pin_label":"System security PIN","tools_sys.system_pin_desc":"Default 4-to-12-digit PIN required before unlocking doors, opening garage covers, or disarming alarms when a Device requires a PIN.","tools_sys.system_pin_aria":"System security PIN (4 to 12 digits)","tools_sys.pin_replace_placeholder":"Enter new PIN to replace\u2026","tools_sys.pin_digits_placeholder":"4 to 12 digits","tools_sys.save_pin":"Save PIN","tools_sys.clear_pin":"Clear PIN","tools_sys.signing_key_label":"Resource URL signing key","tools_sys.signing_key_desc":"Refreshes the signing key for camera, wallpaper, and doorbell audio links and updates connected Devices.","tools_sys.rotate_signing_key":"Rotate signing key","dialogs.app_pinned":"Pinned app","dialogs.app_home_hub":"Home hub","dialogs.app_cameras":"Cameras","dialogs.app_area":"Area control","dialogs.app_music":"Music","dialogs.music_auto_open_desc":"Open Music when playback starts on this Device's default speaker. Wakes from screensaver outside Bedtime mode; stays silent when the screen is off.","dialogs.app_remote":"Remote control","dialogs.app_weather":"Sky & weather","dialogs.app_time":"Time","dialogs.weather_bg_label":"Live weather background","dialogs.weather_bg_desc":"Show the live animated weather sky inside the Sky & weather app. Turn off to use this Device's wallpaper instead.","dialogs.app_calendar":"Calendar","dialogs.app_clock":"Clock face","dialogs.app_tools":"Tools","dialogs.app_games":"Games","dialogs.app_fallback":"Configure app","dialogs.pinned_label":"Pinned shortcuts","dialogs.pinned_desc":"Assign Home Assistant entity quick actions or deep-link any Latter app or subpage (6 buttons per page, swipable vertically).","dialogs.pinned_aria":"Pinned app shortcuts","dialogs.pinned_page_slot":"Page {page}","dialogs.pinned_confirm_mode":"Confirm","dialogs.pinned_one_tap_mode":"1-tap","dialogs.pinned_empty":"No pinned items configured yet. The Pinned icon stays hidden on the App Dock until you add at least one item.","dialogs.home_cats_label":"Home categories","dialogs.home_cats_desc":"Toggle and reorder categories shown in the Home hub. The first available category opens by default; categories with no configured entity are not displayed.","dialogs.broadcast_speakers_label":"Broadcast speakers","dialogs.broadcast_speakers_desc":"Choose which System broadcast speakers this Device announces to. The calling Device's own speaker and displays in Bedtime mode are skipped automatically.","dialogs.broadcast_speakers_empty_system":"No broadcast speakers configured in System shared entities yet.","dialogs.camera_default_view_desc":"Layout shown when opening the Cameras app.","dialogs.camera_framing_desc":"Show the full frame uncropped or fill the display.","dialogs.camera_carousel_interval_desc":"How often Carousel advances to the next camera.","dialogs.camera_stream_mode_desc":"Balances live video frame rate against network bandwidth and battery.","dialogs.camera_doorbell_popup_desc":"Choose whether doorbell rings open a still snapshot or live video.","dialogs.camera_visible_label":"Visible cameras","dialogs.camera_visible_desc":"Toggle and reorder cameras shown in the Cameras app on this Device. Leave all enabled to follow Shared entities automatically.","dialogs.camera_carousel_label":"Carousel cameras","dialogs.camera_carousel_desc":"Choose and reorder which visible cameras rotate in Carousel view.","dialogs.cameras_empty_system":"No cameras configured in Shared entities yet.","dialogs.area_cats_label":"Area categories","dialogs.area_cats_desc":"Toggle and reorder categories shown on the Area screen. The first available category opens by default; categories with no entities in the active Area are not displayed.","dialogs.remote_group_label":"Remote control scope","dialogs.remote_group_desc":"Choose which remotes appear on this Device's Remote screen.","dialogs.remote_follow_area":"Follow the active Area","dialogs.remote_group_option":"Group: {name}","dialogs.remote_all_system":"All System remotes","dialogs.remote_missing_group":"Missing group ({id})","dialogs.manage_remote_groups":"Manage remote groups","dialogs.local_clock_label":"Local clock label","dialogs.local_clock_desc":"Optional custom label shown above local time on the Clock tab.","dialogs.optional_label_placeholder":"Optional label\u2026","dialogs.show_utc_label":"Show UTC clock","dialogs.show_utc_desc":"Pin a live 24-hour UTC reference row to this Device's Clock tab.","dialogs.world_clocks_label":"World clocks","dialogs.world_clocks_desc":"Configure up to 4 custom-labeled time zones (UTC-12:00 to UTC+14:00) shown on this Device's Clock tab.","dialogs.world_clocks_aria":"Configured world clocks","dialogs.world_clock_city_label":"World clock {index} city label","dialogs.world_clock_zone_label":"World clock {index} time zone","dialogs.city_label_placeholder":"Enter city or label\u2026","dialogs.new_city_label":"New city label","dialogs.add_time_zone":"Add time zone","dialogs.max_world_clocks":"Maximum 4 world clocks added","dialogs.select_tz_placeholder":"Select a time zone (UTC-12 to UTC+14)\u2026","dialogs.toast_enter_city":"Enter a city or label for this world clock","dialogs.toast_select_tz":"Select a time zone for this world clock","dialogs.toast_dup_world_clock":"That world clock is already added","dialogs.toast_city_empty":"City label cannot be empty","dialogs.calendar_lookahead_label":"Overview lookahead","dialogs.calendar_lookahead_desc":"Number of upcoming days shown on the Overview tab (days with no events are omitted).","dialogs.calendar_week_start_label":"Start week on","dialogs.calendar_week_start_desc":"First column shown in Week and Month views.","dialogs.tools_label":"Tools","dialogs.tools_desc":"Toggle and reorder utilities shown in the Tools launcher.","dialogs.games_label":"Games","dialogs.games_desc":"Toggle and reorder games shown in the Games launcher.","dialogs.sc_edit_dock":"Edit custom dock shortcut","dialogs.sc_edit_pinned":"Edit pinned shortcut","dialogs.sc_add_dock":"Add custom dock shortcut","dialogs.sc_add_pinned":"Add pinned shortcut","dialogs.sc_type_aria":"Shortcut type","dialogs.sc_tab_subpage":"Subpage","dialogs.sc_tab_app_page":"App or page","dialogs.sc_tab_entity":"Home Assistant entity","dialogs.sc_target_subpage":"Target subpage","dialogs.sc_target_app_page":"Target app or subpage","dialogs.sc_domain_filter":"Domain filter","dialogs.sc_all_domains":"All domains","dialogs.shortcut_entity_label":"Entity","dialogs.sc_action_label":"Action","dialogs.sc_confirm_label":"Confirm before running","dialogs.sc_confirm_dock_desc":"Shows a confirmation prompt before running this action from the App Dock.","dialogs.sc_confirm_pinned_desc":"Require a confirmation tap instead of running immediately on a single tap.","dialogs.sc_custom_label":"Custom label (optional)","dialogs.sc_default_shortcut":"Shortcut","dialogs.sc_default_entity_action":"Entity action","dialogs.sc_icon_label":"Icon (optional MDI override)","dialogs.sc_icon_search_placeholder":"Search {total} icons or tags (e.g. lamp, ac, pet, goodnight)\u2026","dialogs.sc_icon_selected":"Selected: {icon}","dialogs.sc_icon_default":"Default: {icon}","dialogs.sc_icon_no_matches":"No matching icons \u2014 try another keyword","dialogs.sc_icon_showing_subset":"Showing {shown} of {total} matches","dialogs.sc_icon_matches_one":"1 matching icon","dialogs.sc_icon_matches_many":"{count} matching icons","dialogs.sc_icon_popular":"Showing popular icons ({total} searchable)","dialogs.sc_icon_popular_filtered":"Showing popular {style} icons ({total} searchable)","dialogs.sc_icon_style_aria":"Icon weight filter","dialogs.sc_icon_style_all":"All","dialogs.sc_icon_style_solid":"Solid","dialogs.sc_icon_style_outline":"Outline","dialogs.sc_mdi_group_aria":"Material Design Icons","dialogs.sc_badge_style_label":"Icon style","dialogs.sc_badge_style_glass":"Frosted glass","dialogs.sc_badge_style_inverted":"Inverted badge","dialogs.sc_accent_label":"Accent color","dialogs.sc_accent_default":"Default","dialogs.sc_accent_primary":"Theme","dialogs.sc_accent_gold":"Amber","dialogs.sc_accent_green":"Green","dialogs.sc_accent_red":"Red","dialogs.sc_accent_orange":"Orange","dialogs.cw_title":"Add a custom color","dialogs.cw_color_aria":"Color","dialogs.cw_hex_aria":"Hex color","dialogs.cw_name_label":"Name","dialogs.cw_name_placeholder":"e.g. Sunset coral","dialogs.ble_title":"Add a BLE tag","dialogs.ble_body":"A phone, watch, or Bluetooth tag that Latter tracks by Area. Latter displays are adopted under Discovered devices.","dialogs.ble_discovered_label":"Discovered Bluetooth devices","dialogs.ble_enter_manually":"Enter manually\u2026","dialogs.ble_name_label":"Name","dialogs.ble_name_placeholder":"e.g. phone, watch, keys","dialogs.ble_addr_label":"Target address or entity","dialogs.ble_addr_placeholder":"AA:BB:CC:DD:EE:FF, iBeacon UUID, or tracker entity","dialogs.ble_addr_help":"Enter a static BLE MAC address, iBeacon UUID (with optional major:minor), or Home Assistant Companion App or tracker entity.","dialogs.ble_person_label":"Assigned person (optional)","dialogs.save_group_title":"Save custom group","dialogs.save_group_body":"Saves this Device's settings as a reusable Device group and assigns this Device to it.","dialogs.save_group_name_placeholder":"e.g. Nightstands, Guest suites","dialogs.save_group_desc_placeholder":"Optional summary of these settings","confirm.blast_radius_one":"Affects 1 Device","confirm.blast_radius_many":"Affects {count} Devices","confirm.remove_device.title":"Remove {title}?","confirm.remove_device.body":'Removes "{title}" from Latter and deletes its stored Latter preferences and shortcuts. Your ESPHome device stays in Home Assistant.',"confirm.remove_device.confirm":"Remove Device","confirm.reset_device.title":"Reset to defaults?","confirm.reset_device.body":"Wi-Fi and pairing are kept, so the Device rejoins Home Assistant automatically. Its ESPHome binding and Music Assistant player link are kept too.","confirm.reset_device.device_settings":"Settings saved on the Device","confirm.reset_device.device_settings_desc":"Erases everything saved on the Device and restarts it.","confirm.reset_device.latter_options":"Latter settings for this Device","confirm.reset_device.latter_options_desc":"Resets shortcuts, group assignment, and Latter preferences for this Device to factory defaults.","confirm.reset_device.confirm":"Reset","confirm.restore_backup.title":"Restore from backup?","confirm.restore_backup.body":"Overwrites current Latter settings with the selected JSON backup bundle.","confirm.restore_backup.confirm":"Restore backup","confirm.delete_group.title":'Delete group "{name}"?',"confirm.delete_group.body":"Devices currently assigned to this group keep their settings and switch to Custom.","confirm.delete_group.confirm":"Delete group","confirm.reset_group.title":'Reset "{name}" to preset defaults?',"confirm.reset_group.body":"Restores the built-in power, wake, and scope defaults for this group and applies them to assigned Devices.","confirm.reset_group.confirm":"Reset preset","confirm.rotate_signing_key.title":"Rotate URL signing key?","confirm.rotate_signing_key.body":"Invalidates active signed wallpaper, camera snapshot, and doorbell audio URLs until Devices receive the next state push.","confirm.rotate_signing_key.confirm":"Rotate signing key","confirm.delete_photo.title":'Delete photo "{name}"?',"confirm.delete_photo.body":"Permanently deletes this photo from the System library and removes it from any Device wallpaper or Photo frame pools.","confirm.delete_photo.confirm":"Delete photo","confirm.delete_photos_bulk.title":"Delete {count} photos?","confirm.delete_photos_bulk.body":"Permanently deletes the selected uploaded photos and prunes them from Device wallpaper and Photo frame pools.","confirm.delete_photos_bulk.confirm":"Delete photos","confirm.delete_collection.title":'Delete collection "{name}"?',"confirm.delete_collection.body":"Deletes this collection label. Photos inside stay in your Photo library.","confirm.delete_collection.confirm":"Delete collection","photos.subtitle":"Shared System photo library and collections used for Device wallpapers and Photo frame screensavers.","photos.upload_btn":"Upload photos","photos.import_media_btn":"Import from Media","photos.new_collection_btn":"New collection","photos.new_collection_placeholder":"Collection name (e.g. Family, Landscapes)\u2026","photos.create_collection":"Create","photos.rename_collection_aria":"Rename collection {name}","photos.delete_collection_aria":"Delete collection {name}","photos.rename_collection_placeholder":"Collection name\u2026","photos.filter_all":"All","photos.filter_defaults":"Defaults","photos.filter_my_photos":"My photos","photos.filter_uncategorized":"Uncategorized","photos.search_placeholder":"Search photos by name\u2026","photos.search_aria":"Search photos","photos.select_mode_btn":"Select","photos.done_selecting_btn":"Done selecting","photos.selected_count_one":"1 selected","photos.selected_count_many":"{count} selected","photos.select_all_page":"Select page","photos.clear_selection":"Clear selection","photos.bulk_collection_aria":"Choose collection for selected photos","photos.bulk_choose_collection":"\u2014 Choose collection \u2014","photos.bulk_add_to_collection":"Add to collection","photos.bulk_remove_from_collection":"Remove from collection","photos.bulk_delete_btn":"Delete selected","photos.badge_dynamic":"Dynamic","photos.badge_default":"Default","photos.badge_media":"Media","photos.edit_photo_aria":"Edit photo {name}","photos.select_photo_aria":"Select photo {name}","photos.empty_library":"No photos match this filter. Upload photos or import from Home Assistant Media.","photos.page_status":"Showing {start}\u2013{end} of {total}","photos.prev_page":"Previous","photos.next_page":"Next","photos.created_collection_toast":'Created collection "{name}"',"photos.renamed_collection_toast":'Renamed collection to "{name}"',"photos.deleted_collection_toast":"Deleted collection","photos.updated_photo_toast":"Saved photo changes","photos.deleted_photo_toast":"Deleted photo","photos.bulk_updated_toast":"Updated {count} photo(s)","photos.bulk_deleted_toast":"Deleted {count} photo(s)","photo_edit.title":"Edit photo","photo_edit.name_label":"Photo name","photo_edit.name_placeholder":"Enter a photo name\u2026","photo_edit.crop_hint":"Drag to pan and use the slider to zoom. Originals are kept intact so every display shape stays sharp.","photo_edit.aspect_aria":"Preview display shape","photo_edit.aspect_square":"Square + circle","photo_edit.aspect_round":"Round","photo_edit.aspect_widescreen":"Widescreen","photo_edit.zoom_label":"Zoom","photo_edit.reset_crop":"Reset crop","photo_edit.collections_label":"Collections","photo_edit.collections_empty":"Create a collection in Photos to organize photos into albums.","photo_edit.dimensions_meta":"{width} \xD7 {height} px","photo_edit.source_media":"Imported from {path}","photo_upload.title":"Upload photos","photo_upload.dropzone_title":"Drag & drop photos here, or browse","photo_upload.dropzone_hint":"JPEG, PNG, or WebP up to 15 MB each. Select multiple files at once.","photo_upload.choose_files":"Choose files","photo_upload.add_more":"Add more files","photo_upload.collection_label":"Add all to collection","photo_upload.no_collection":"\u2014 No collection \u2014","photo_upload.upload_all_one":"Upload photo","photo_upload.upload_all_many":"Upload all ({count})","photo_upload.uploading_progress":"Uploading {current} of {total} \u2014 {percent}%","photo_upload.remove_staged_aria":"Remove {name} from upload queue","photo_upload.select_staged_aria":"Adjust crop for {name}","photo_upload.uploaded_one_toast":"Uploaded 1 photo","photo_upload.uploaded_many_toast":"Uploaded {count} photos","photo_upload.file_too_large":'Skipped "{name}" (exceeds 15 MB limit)',"media_import.title":"Import from Home Assistant Media","media_import.subtitle":"Browse local Media folders and mounted NAS shares configured in Home Assistant.","media_import.root_label":"Media folder","media_import.up_folder":"Up","media_import.select_all_folder":"Select all in folder","media_import.clear_folder_selection":"Clear selection","media_import.already_imported":"Imported","media_import.too_large":"Over 15 MB","media_import.empty_folder":"No subfolders or supported images found in this folder.","media_import.empty_roots":"No Home Assistant Media directories are configured.","media_import.collection_label":"Add to collection","media_import.new_from_folder":"New collection from folder name","media_import.new_collection_name":"New collection name","media_import.import_btn_one":"Import 1 photo","media_import.import_btn_many":"Import {count} photos","media_import.importing_btn":"Importing\u2026","media_import.summary_toast":"Imported {imported} photo(s){skippedSuffix}{failedSuffix}","media_import.skipped_suffix":" ({count} duplicate skipped)","media_import.failed_suffix":" ({count} failed)","photo_picker.title_wallpaper":"Choose wallpaper","photo_picker.title_screensaver":"Choose Photo frame photos","photo_picker.mode_aria":"Photo selection mode","photo_picker.mode_photos":"Photos","photo_picker.mode_collection":"Collection","photo_picker.collection_label":"Photo collection","photo_picker.custom_hint":"Pick one photo for a static image, or multiple photos to rotate through.","photo_picker.custom_selected_one":"1 photo selected","photo_picker.custom_selected_many":"{count} photos selected","photo_picker.apply_btn":"Apply selection","photo_picker.empty":"No photos available for this mode yet. Upload photos to get started.","groups.pool_off":"Off","groups.pool_all":"All photos","groups.pool_defaults":"Built-in defaults","groups.pool_uploads":"My uploaded photos","groups.pool_collection_prefix":"Collection: {name}","groups.pool_photo_prefix":"Photo: {name}","groups.screensaver_pool_label":"Photo frame source","groups.wallpaper_pool_label":"Wallpaper source","confirm.reset_dock.title":"Reset App Dock to default?","confirm.reset_dock.body":"Restores the default native apps on the App Dock and removes custom dock shortcuts on this Device.","confirm.reset_dock.confirm":"Reset dock","confirm.clear_ble_signature.title":"Clear BLE signature for {area}?","confirm.clear_ble_signature.body":"Removes captured RSSI calibration samples for {area} and reverts to path-loss estimation.","confirm.clear_ble_signature.confirm":"Clear signature","confirm.clear_pin.title":"Clear security PIN?","confirm.clear_pin.body":"Removes the configured security PIN. Perimeter actions governed by Require PIN stay blocked until a new PIN is set.","confirm.clear_pin.confirm":"Clear PIN","confirm.apply_batch.title":"Apply staged changes to {count} Devices?","confirm.apply_batch.body":"Pushes {settingCount} staged setting changes to {count} target Devices.","confirm.apply_batch.confirm":"Apply changes","offline.device_banner_title":"Device is offline or hibernating","offline.device_sleeping_title":"Device is sleeping","offline.device_banner_body":"Settings saved here are queued in Home Assistant and sync automatically when this Device wakes or reconnects. Live quick actions are unavailable while offline.","offline.ble_tx_off_title":"BLE transmitter not active ({state})","offline.ble_tx_off_body":"Enable the BLE Transmitter sensor in the Home Assistant Companion App on this phone so Bluetooth proxies can detect its Area.","card.status":"Status","card.quick_actions":"Quick actions","card.assignments":"Assignments","card.timers_alarms":"Timers & alarms","card.sensors_controls":"Sensors & controls","card.wallpapers":"Wallpapers","card.brightness":"Brightness","card.colors":"Colors","card.screensaver":"Screensaver","card.home_screen":"Home screen","card.app_dock":"App Dock","card.diagnostics":"Diagnostics","card.developer_telemetry":"Developer & telemetry","card.replace_hardware":"Replace hardware","card.replace_hardware_body":"Replaced a physical board or reflashed under a new ESPHome node? Use Reconfigure on this Device entry in Home Assistant Integrations to rebind its hardware identity while keeping all shortcuts, Area rules, and settings.","card.danger_zone":"Danger zone","devices.inventory_heading":"Inventory","devices.col_device":"Device","devices.col_model":"Model","devices.col_area":"Area","devices.col_group":"Group","devices.col_status":"Status","devices.filter_aria":"Filter managed Devices by category","devices.all":"All Devices","devices.online":"Online Devices","devices.roaming":"Roaming Devices","devices.stationary":"Stationary Devices","devices.latter_displays":"Latter displays","devices.ble_tracked":"BLE-tracked Devices","devices.phones":"Phones","devices.ble_tags":"BLE tags","devices.assigned_person":"Assigned to a person","devices.updates_available":"Updates available","devices.group_prefix":"Group: {name}","devices.empty_filtered":"No Devices match this category.","devices.empty_zero_title":"No managed Devices yet","devices.empty_zero_body":"Adopt discovered Latter displays, add Bluetooth tags for Area presence, or configure System Area sensor fusion.","devices.open_discovered":"Open Discovered","devices.open_area_presence":"Configure Area presence","discovered.latter_devices":"Latter Devices","discovered.bluetooth_devices":"Bluetooth devices","discovered.empty_latter":"No unconfigured Latter Devices found in Home Assistant. Newly added ESPHome Devices running Latter firmware appear here automatically.","discovered.web_installer":"Open Web Installer","discovered.getting_started":"Getting started guide","discovered.ignored_count":"Ignored ({count})","discovered.default_latter_title":"Latter Device","discovered.default_latter_model":"Latter ESPHome Device","discovered.default_ble_kind":"BLE device","discovered.meta_node":"Node: {node}","discovered.meta_area":"Area: {area}","discovered.meta_nearest_area":"Nearest Area: {area}","discovered.group_select_aria":"Device group for {title}","discovered.auto_group_option":"Auto ({group})","discovered.person_select_aria":"Assigned person for {title}","discovered.ignore_aria":"Ignore {title}","discovered.restore_aria":"Restore {title}","discovered.search_ble_aria":"Search discovered Bluetooth devices","discovered.search_ble_placeholder":"Search name, address, or Area\u2026","discovered.filter_ble_aria":"Filter discovered Bluetooth devices","discovered.all_ble":"All Bluetooth devices","discovered.phones_trackers":"Phones & trackers","discovered.named_ble":"Named BLE advertisements","discovered.sort_ble_aria":"Sort discovered Bluetooth devices","discovered.sort_name":"Sort: Name (A\u2013Z)","discovered.sort_rssi":"Sort: Signal strength","discovered.sort_area":"Sort: Nearest Area","discovered.pause_list":"Pause list","discovered.resume_list":"Resume list","discovered.paused_hint":"List updates paused ({count} shown). Select Resume list to refresh.","discovered.empty_ble_filtered":"No Bluetooth devices match this filter.","discovered.empty_ble_none":"No unadopted Bluetooth devices nearby.","discovered.adopted_toast":'Adopted "{title}"',"discovered.ignored_toast":'Ignored "{title}"',"discovered.restored_toast":'Restored "{title}" to discovered list',"wp_gallery.builtin":"Built-in","wp_gallery.uploading":"Uploading\u2026","wp_gallery.upload_progress_aria":"Wallpaper upload progress","dev_overview.waiting_for_reading":"Waiting for reading","dev_overview.tile_area":"Area","dev_overview.tile_current_area":"Current Area","dev_overview.tile_closest_proxy":"Closest proxy","dev_overview.ble_presence_meta":"BLE presence","dev_overview.tile_battery":"Battery","dev_overview.tile_power":"Power","dev_overview.tile_ble_signal":"BLE signal","dev_overview.tile_wifi_signal":"Wi-Fi signal","dev_overview.tile_ble_target":"BLE target","dev_overview.ble_address_meta":"Bluetooth address","dev_overview.tile_firmware":"Firmware","dev_overview.qa_find_my":"Find my Device","dev_overview.qa_trigger_va":"Trigger voice assistant","dev_overview.qa_activate_screensaver":"Activate screensaver","dev_overview.qa_exit_screensaver":"Exit screensaver","dev_overview.qa_restart":"Restart Device","dev_overview.restart_device":"Restart Device","dev_overview.restart_device_desc":"Reboots this Device; Wi-Fi and active sessions reconnect automatically.","dev_overview.restart_btn":"Restart","dev_overview.empty_quick_actions":"No live actions reported by this Device.","dev_overview.device_group_label":"Device group","dev_overview.device_group_custom_desc":"Uses individual operational settings; save as a reusable group or pick an existing preset.","dev_overview.device_group_preset_desc":"Applies shared operational settings (power, wake word, brightness, BLE).","dev_overview.device_category_label":"Device category","dev_overview.device_category_desc":"Classifies this Bluetooth Device under Phones or BLE tags across Managed devices.","dev_overview.auto_category_option":"Auto ({category})","dev_overview.assigned_person_label":"Assigned person","dev_overview.assigned_person_desc":"Links this Device's Area presence to a Home Assistant person entity.","dev_overview.unassigned_option":"\u2014 Unassigned \u2014","dev_overview.remote_group_label":"Remote control scope","dev_overview.remote_group_desc":"Controls which TV and AV remotes appear in the Remote app.","dev_overview.remote_follow_area":"Follow Area","dev_overview.remote_all_system":"All System remotes","dev_overview.ringing_alert_text":"An alarm or timer is ringing on this Device.","dev_overview.dismissed_ringing_toast":"Dismissed ringing alert","dev_overview.active_timer_label":"Active timer","dev_overview.no_active_timer":"No active timer","dev_overview.running":"Running","dev_overview.paused":"Paused","dev_overview.cancel_timer":"Cancel timer","dev_overview.cancelled_timer_toast":"Cancelled timer","dev_overview.stopwatch_label":"Stopwatch","dev_overview.not_running":"Not running","dev_overview.reset_stopwatch":"Reset stopwatch","dev_overview.reset_stopwatch_toast":"Reset stopwatch","dev_overview.alarms_label":"Alarms","dev_overview.alarms_enabled_summary":"{count} enabled \u2022 {nextTime}","dev_overview.alarms_desc":"Syncs 2-way with on-device alarm edits (1-minute precision).","dev_overview.alarms_group_aria":"Device alarms","dev_overview.alarm_time_label":"Alarm {index} time","dev_overview.alarm_schedule_label":"Alarm {index} schedule","dev_overview.alarm_rec_daily":"Daily","dev_overview.alarm_rec_weekdays":"Weekdays","dev_overview.alarm_rec_weekends":"Weekends","dev_overview.alarm_rec_once":"Once","dev_display.card_voice_assistant":"Voice assistant","dev_display.bedtime_brightness_override_note":"Bedtime mode is currently active and overriding screen brightness.","dev_display.bright_brightness_label":"Bright brightness","dev_display.dark_brightness_label":"Dark brightness","dev_display.ambient_live_status":"{area} \xB7 {lux} lx ({level}% ambient)","dev_display.ambient_fallback_status":"No ambient light sensor in {area} \u2014 using Sun synchronized fallback.","dev_display.ambient_unassigned_status":"Locate or assign this Device to an Area to use ambient light.","dev_display.screensaver_preview_desc":"Starts the screensaver on this Device immediately.","dev_display.screensaver_exit_desc":"Wakes the display and exits the active screensaver immediately.","dev_display.preview_btn":"Preview","dev_display.exit_screensaver_btn":"Exit screensaver","dev_display.screensaver_photo_clock_desc":"Draws a compact subtle clock in the corner while displaying photos.","dev_display.screensaver_pool_label":"Photo frame photos","dev_display.screensaver_pool_empty":"No photos selected \u2014 choose photos or a collection.","dev_display.screensaver_choose_photos":"Choose photos\u2026","dev_display.screensaver_shuffle_desc":"Randomizes photo order instead of advancing alphabetically.","dev_display.custom_color_label":"Custom color","dev_display.custom_color_desc":"Used when Color profile is set to Custom.","dev_display.current_color_option":"Current ({hex})","dev_display.add_color_btn":"Add color","dev_display.wallpapers_subtitle":"Shared photo library and collections cropped automatically for this display.","dev_display.choose_wallpaper":"Choose wallpaper\u2026","dev_display.manage_photo_library":"Manage photo library","dev_display.pool_single_meta":"Single photo \u2022 {name}","dev_display.pool_collection_meta":"Collection: {collection} ({count} photos)","dev_display.pool_collection_one_meta":"Collection: {collection} (1 photo)","dev_display.pool_custom_meta":"Custom selection ({count} photos)","dev_display.pool_custom_one_meta":"Custom selection (1 photo)","dev_display.pool_off_meta":"Off \u2014 no photos selected.","dev_display.wp_override_home_and_weather":"Live weather background is active on Home and Sky & weather \u2014 wallpapers appear on other screens.","dev_display.wp_override_home_only":"Weather background is enabled on Home \u2014 wallpapers appear across other screens.","dev_display.wp_override_weather_only":"Live weather background is active in Sky & weather \u2014 wallpapers appear on Home and other screens.","dev_display.open_interface":"Open Interface","dev_display.turn_off_wallpaper":"Turn off wallpaper","dev_display.rotation_interval_label":"Rotation interval","dev_display.rotation_interval_aria":"Wallpaper rotation interval","dev_display.rot_0":"Do not rotate","dev_display.rot_5":"Every 5 minutes","dev_display.rot_15":"Every 15 minutes","dev_display.rot_30":"Every 30 minutes","dev_display.rot_60":"Every hour","dev_display.rot_360":"Every 6 hours","dev_display.rot_1440":"Once a day","dev_interface.enable_home_desc":"Provides the Home screen and App Dock. Turn off to lock this Device to a single start screen app.","dev_interface.start_screen_multi_desc":"Choose the screen shown on startup. Swipe up from the bottom to return to Home.","dev_interface.start_screen_single_desc":"Single-app screen shown at all times while the Home screen is disabled.","dev_interface.time_format_desc":"Applies 12-hour or 24-hour time across Home, alarms, calendar, and schedules.","dev_interface.home_clock_tap_desc":"Choose whether tapping the clock readout on Home opens the Time app or the standalone clock face.","dev_interface.clock_face_desc":"Visual style for the standalone clock face screen.","dev_interface.home_date_tap_desc":"Choose whether tapping the date readout on Home opens Day view or Overview in the Calendar app.","dev_interface.return_timeout_desc":"Resets idle screens back to Home unless media is playing or a live activity is active.","dev_interface.wake_greeting_desc":"Shows a brief morning, afternoon, or evening greeting after waking from standby.","dev_interface.weather_bg_desc":"Replaces the Home screen backdrop with a live sky matching current conditions.","dev_interface.sun_moon_label":"Sun & Moon","dev_interface.sun_moon_desc":"Choose which sky bodies appear on the live weather background.","dev_interface.activity_card_desc":"Shows live timers, alarms, media queue, stopwatch, and next calendar event on Home.","dev_interface.activity_sources_desc":"Choose and reorder which live items appear in the Activity card.","dev_interface.activity_src_calendar":"Calendar","dev_interface.activity_src_music_queue":"Music queue","dev_interface.activity_src_stopwatch":"Stopwatch","dev_interface.activity_src_alarms":"Alarms","dev_interface.activity_src_timers":"Timers","dev_interface.app_dock_desc":"Toggle, drag to reorder, and configure apps on the App Dock, or add custom subpage and Home Assistant entity shortcuts. Pinned hides automatically when empty.","dev_interface.active_dock_aria":"Active on App Dock","dev_interface.show_on_dock_aria":"Show {title} on App Dock","dev_interface.settings_title":"Settings","dev_interface.settings_locked_meta":"Always shown last on the App Dock","dev_interface.hidden_from_dock":"Hidden from dock","dev_interface.pinned_empty_meta":"Empty \u2014 auto-hidden on dock","dev_interface.pinned_count_meta":"{count} {shortcutWord} \u2022 {pages} {pageWord}","dev_interface.word_shortcut_one":"shortcut","dev_interface.word_shortcut_many":"shortcuts","dev_interface.word_page_one":"page","dev_interface.word_page_many":"pages","dev_interface.music_meta":"Art: {art} \u2022 Albums: {albums}","dev_interface.cameras_empty_meta":"No cameras configured","dev_interface.cameras_meta_one":"{view} \u2022 {framing} \u2022 1 camera","dev_interface.cameras_meta_many":"{view} \u2022 {framing} \u2022 {count} cameras","dev_interface.categories_enabled_one":"1 category enabled","dev_interface.categories_enabled_many":"{count} categories enabled","dev_interface.remote_follow_area":"Follow the active Area","dev_interface.remote_all":"All System remotes","dev_interface.weather_meta_live_sky":"Live weather sky","dev_interface.weather_meta_wallpaper":"Uses device wallpaper","dev_interface.time_utc_world_one":"UTC + 1 world clock","dev_interface.time_utc_world_many":"UTC + {count} world clocks","dev_interface.time_world_one":"1 world clock","dev_interface.time_world_many":"{count} world clocks","dev_interface.time_local_utc":"Local time + UTC","dev_interface.time_local":"Local time","dev_interface.clock_24h":"24-hour","dev_interface.clock_12h":"12-hour","dev_interface.calendar_meta":"{days}-day lookahead \u2022 Starts {weekday}","dev_interface.tools_enabled_one":"1 tool enabled","dev_interface.tools_enabled_many":"{count} tools enabled","dev_interface.games_enabled_one":"1 game enabled","dev_interface.games_enabled_many":"{count} games enabled","dev_interface.custom_route_meta":"Custom \u2022 {target}","dev_interface.custom_entity_confirm_meta":"Custom \u2022 {action} \u2022 Confirm \u2022 {target}","dev_interface.custom_entity_tap_meta":"Custom \u2022 {action} \u2022 1-tap \u2022 {target}","dev_audio.card_voice_wake":"Voice assistant & wake word","dev_audio.card_sound_playback":"Sound & playback","dev_audio.vfm_desc":"Updates this roaming Device's Home Assistant Area when BLE presence settles in a new Area, so Area-less voice commands target where you are.","dev_audio.vfm_delay_label":"Voice Follows Me delay","dev_audio.vfm_delay_desc":"How long a BLE-detected Area stays stable before moving the Device (3 to 60 seconds).","dev_audio.ww_sensitivity_summary":"Wake word sensitivity (per model)","dev_audio.default_speaker_label":"Default speaker","dev_audio.default_speaker_desc":"Primary speaker controlled from Music and Home when this Device starts up.","dev_audio.default_speaker_auto":"\u2014 Automatic (built-in or Area) \u2014","dev_audio.ma_player_label":"Music Assistant player","dev_audio.ma_player_unmatched_desc":"Automatic match did not find {entity} in Music Assistant. Choose this Device's player for library playback, queues, and lyrics.","dev_audio.ma_player_manual_desc":"Linked manually ({entity} was not used). Clear to return to automatic matching.","dev_audio.ma_player_fallback_target":"this Device's player","dev_audio.ma_player_auto":"\u2014 Automatic match \u2014","dev_audio.area_handoff_desc":"Transfers active Music Assistant playback when this Device moves to or selects another Area.","dev_power.card_sleep_wake":"Sleep & wake","dev_power.card_bedtime":"Bedtime mode","dev_power.card_bedtime_subtitle":"Turns off or dims the display overnight and silences non-critical notification chimes.","dev_power.card_power_battery":"Power & battery","dev_power.empty":"No sleep or battery entities reported by this Device.","dev_presence.card_area_tracking":"Area tracking","dev_presence.card_ble_identity":"BLE identity","dev_presence.track_ble_label":"Track Area with BLE proxies","dev_presence.track_ble_desc":"Uses Home Assistant Area-assigned Bluetooth proxies to locate this Device automatically. Turn off to pin it to one assigned Area.","dev_presence.auto_switch_desc":"Switches the Device's active Area controls automatically when BLE detects a move.","dev_presence.fallback_area_label":"Fallback Area","dev_presence.fallback_area_desc":"Default Home Assistant Area when no Bluetooth proxy is in range.","dev_presence.fallback_area_auto":"\u2014 Automatic (ESPHome Area) \u2014","dev_presence.assigned_area_label":"Assigned Area","dev_presence.assigned_area_desc":"Pins this Device's Area controls and Home Assistant Device Area to one location.","dev_presence.target_addr_label":"BLE target address or entity","dev_presence.target_addr_placeholder":"AA:BB:CC:DD:EE:FF or device_tracker.phone_ble","dev_presence.target_addr_help":"Leave blank on Latter displays to track their built-in BLE beacon MAC automatically.","dev_presence.ref_power_label":"Reference power (1 meter)","dev_presence.ref_power_placeholder_detected":"Auto ({dbm} dBm)","dev_presence.ref_power_help":"Leave blank to use auto-detected beacon power in dBm, or enter -90 to -30 dBm to calibrate this Device.","dev_presence.companion_low_title":"Companion App low-power beacon detected","dev_presence.companion_low_body":"This phone is advertising at {txPower} power{modeSuffix}.{refSuffix} Setting Transmit Power to Medium or High and Advertise Mode to Balanced in the Home Assistant Companion App improves multi-Area accuracy through walls.","dev_presence.companion_mode_suffix":" ({mode} mode)","dev_presence.companion_ref_suffix":" Latter automatically compensates its 1 m reference power ({dbm} dBm).","dev_presence.companion_default_power":"default","dev_presence.ibeacon_uuid_label":"iBeacon UUID","dev_presence.ibeacon_uuid_placeholder":"Generated automatically per System","dev_tools.ble_signal":"BLE signal","dev_tools.ble_target":"BLE target","dev_tools.model":"Model","dev_tools.esphome_node":"ESPHome node","dev_tools.firmware_version":"Firmware version","dev_tools.latter_sdk":"Latter SDK","dev_tools.wifi_signal":"Wi-Fi signal","dev_tools.ip_address":"IP address","dev_tools.mac_address":"MAC address","dev_tools.diagnostics_file_label":"Diagnostics file","dev_tools.diagnostics_file_desc":"Downloads redacted Home Assistant diagnostics for troubleshooting.","dev_tools.backup_row_label":"Device backup","dev_tools.backup_row_desc":"Downloads this Device's Latter configuration and settings as JSON.","dev_tools.perimeter_subtitle":"Governs unlocking doors, disarming alarms, and opening garage or gate covers from this Device.","dev_tools.pin_policy_desc_prefix":"Auto requires a PIN on stationary wall panels when configured and allows roaming personal Devices. Effective policy:","dev_tools.security_pin_label":"Security PIN","dev_tools.security_pin_desc":"Write-only 4 to 12 digit numeric PIN verified by Home Assistant when the on-device keypad prompts. Never shown again after saving.","dev_tools.pin_input_aria":"New security PIN (4 to 12 digits)","dev_tools.pin_placeholder_replace":"Enter new PIN to replace\u2026","dev_tools.pin_placeholder_new":"4 to 12 digits","dev_tools.save_pin":"Save PIN","dev_tools.clear_pin":"Clear PIN","dev_tools.reconfigure_in_ha":"Reconfigure in Home Assistant","dev_tools.reset_defaults_label":"Reset to defaults","dev_tools.reset_defaults_desc":"Resets on-device preferences and/or Latter settings while keeping Wi-Fi and Home Assistant pairing.","dev_tools.remove_device_label":"Remove Device","dev_tools.remove_device_desc":"Removes this Device from Latter. Your ESPHome device stays in Home Assistant.","dev_tools.telem_uptime":"Session uptime","dev_tools.profiler_label":"Telemetry profiler","dev_tools.profiler_desc":"Streams frame and subsystem timing logs over ESPHome logs for troubleshooting.","dev_tools.refresh_telemetry_label":"Runtime telemetry","dev_tools.refresh_telemetry_desc":"Requests an immediate RAM, PSRAM, and Wi-Fi link snapshot from this Device.","dev_tools.refresh_telemetry_toast":"Requested telemetry snapshot","dev_tools.telem_int_ram":"Internal RAM (free / min / largest)","dev_tools.telem_psram_min":"PSRAM low-water mark","dev_tools.telem_ble_beacon":"BLE beacon radio","dev_tools.telem_last_reset":"Last reset","dev_tools.telem_wifi_disc":"Wi-Fi disconnects","dev_tools.telem_beacon_timeouts":" ({count} beacon timeouts)","dev_tools.telem_wifi_avg_min":"Wi-Fi avg / min","dev_tools.telem_ha_sessions":"Home Assistant sessions","dev_tools.telem_max_gap":" (max gap {duration})","dev_tools.telem_light_sleep":"Light sleep duty","dev_tools.telem_cycles":" ({count} cycles)","dev_tools.telem_nvs_writes":"NVS flash writes","dev_tools.telem_nvs_value":"{writes} writes ({erases} erases, {maxMs} ms max)","dev_tools.telem_board":"Hardware board","dev_tools.telem_processor":"Processor & PSRAM","dev_tools.telem_psram_suffix":" \u2022 {mb} MB PSRAM","dev_tools.telem_display_panel":"Display panel","dev_tools.telem_headless":"Headless","dev_tools.telem_traits":"Hardware traits","dev_tools.trait_touch":"Touch","dev_tools.trait_mic":"Mic","dev_tools.trait_speaker":"Speaker","dev_tools.trait_audio":"Audio","dev_tools.trait_imu":"IMU","dev_tools.trait_battery":"Battery","dev_tools.trait_wearable":"Wearable","dev_tools.trait_stationary":"Stationary"},ns={wake_word_mode:"Wake word mode",tap_to_wake:"Tap to wake",pickup_to_wake:"Pickup to wake",battery_screen_timeout:"Battery screen timeout",docked_idle_timeout:"Docked idle timeout",battery_hibernate_timeout:"Battery hibernate timeout",screensaver_mode:"Screensaver mode",screensaver_style:"Screensaver style",screensaver_photo_clock:"Show subtle clock",bedtime_active:"Bedtime mode",do_not_disturb:"Do not disturb",bedtime_display:"Idle display in bedtime",bedtime_brightness:"Bedtime brightness",bedtime_schedule:"Bedtime schedule",bedtime_start_hour:"Bedtime starts",bedtime_end_hour:"Bedtime ends",auto_brightness_mode:"Auto brightness mode",manual_brightness:"Manual brightness",day_brightness:"Day brightness",night_brightness:"Night brightness",day_start_hour:"Day start hour",night_start_hour:"Night start hour",color_profile:"Color profile",va_visual_profile:"Visual profile",home_screen_enabled:"Enable Home screen",start_screen:"Start screen",return_to_home_timeout:"Return to Home timeout",clock_face:"Clock face",time_format:"Time format",weather_background:"Live weather background on Home",weather_app_background:"Live weather background",home_sun:"Sun",home_moon:"Moon",wake_greeting:"Wake greeting",album_art_style:"Album art style",music_overlay_style:"Overlay style",music_auto_open:"Auto-open on play",album_sort_order:"Album sort order",artist_album_sort_order:"Artist album sort order",podcast_sort_order:"Podcast sort order",ww_sens_okay_nabu:"Okay Nabu sensitivity",ww_sens_hey_luna:"Hey Luna sensitivity",ww_sens_hey_jarvis:"Hey Jarvis sensitivity",ww_sens_hey_mycroft:"Hey Mycroft sensitivity",ww_sens_alexa:"Alexa sensitivity",wake_screen_on_assist:"Wake screen on Assist",alert_volume:"Alert volume",volume_step_size:"Volume step size",game_sound_effects:"Game sound effects",ble_beacon_mode:"BLE beacon mode",weather_sim_condition:"Weather simulation",home_clock_tap_action:"Home time tap",home_date_tap_action:"Home date tap",local_clock_label:"Local clock label",show_utc_clock:"Show UTC clock",world_clocks:"World clocks",alarms_summary:"Alarms",calendar_lookahead_days:"Overview lookahead",calendar_week_start:"Start week on",camera_default_view:"Default view",camera_carousel_interval:"Carousel interval",camera_framing:"Video framing",camera_stream_mode:"Stream mode",camera_doorbell_popup:"Doorbell ring popup",native_ble_tracking:"BLE Area tracking",ble_auto_switch:"Auto-switch active Area",sync_device_area:"Voice Follows Me",area_follow_dwell_s:"Area follow dwell",area_handoff:"Media Area handoff",security_pin_policy:"Perimeter security policy",wallpaper_mode:"Wallpaper mode",wallpaper_source:"Wallpaper",wallpaper_collection:"Wallpaper collection",wallpaper_cycle_minutes:"Wallpaper rotation",screensaver_photo_mode:"Photo frame pool",screensaver_photo_source:"Photo frame photo",screensaver_photo_collection:"Photo frame collection",screensaver_cycle_minutes:"Photo frame rotation",screensaver_shuffle:"Shuffle photos",device_custom_color:"Custom color",device_remote_group:"Remote control scope",activity_card:"Show Activity card",activity_sources:"Activity card sources",area_categories:"Area categories",home_categories:"Home categories",tools_items:"Enabled tools",games_items:"Enabled games",broadcast_speaker_entities:"Broadcast speakers",camera_visible_entities:"Visible cameras",camera_carousel_entities:"Carousel cameras"},ss={"Docked Only":"Docked only","Always On":"Always on",Disabled:"Disabled","Single Tap":"Single tap","Double Tap":"Double tap",Never:"Never","10s":"10 seconds","15s":"15 seconds","30s":"30 seconds","60s":"60 seconds","1 min":"1 minute","2 min":"2 minutes","5 min":"5 minutes","10 min":"10 minutes","15 min":"15 minutes","30 min":"30 minutes","Screen Off":"Screen off","Ambient Clock":"Ambient clock","Photo Frame":"Photo frame",Aurora:"Aurora",Starfield:"Starfield","Digital Rain":"Digital rain",Fireworks:"Fireworks","Sun Synchronized":"Sun synchronized","Time Schedule":"Time schedule","Ambient Light":"Ambient light","Steel Blue":"Steel blue",Pink:"Pink",Blue:"Blue",Green:"Green",Custom:"Custom",Nebula:"Nebula",Solaris:"Solaris",Rings:"Rings","Light Bar":"Light bar","Dot Wave":"Dot wave",Home:"Home",Pinned:"Pinned","Time App":"Time app",Calendar:"Calendar","Clock Face":"Clock face",Media:"Media","Home Hub":"Home hub","Area Controls":"Area controls",Remote:"Remote",Weather:"Weather",Cameras:"Cameras",Games:"Games",Tools:"Tools","Minimal Digital":"Minimal digital","Modern Analog":"Modern analog","Hybrid Digital":"Hybrid digital","12-Hour (AM/PM)":"12-hour (AM/PM)","24-Hour":"24-hour","Day View":"Day view",Overview:"Overview",Sunday:"Sunday",Monday:"Monday","Full Screen":"Full screen",Letterbox:"Letterbox",Standard:"Standard",None:"None","Art Only":"Art only","Art + Metadata":"Art + metadata","Always Visible":"Always visible","Now Playing":"Now playing",Lyrics:"Lyrics",Off:"Off",Alphabetical:"Alphabetical","Newest on Top":"Newest on top","Oldest on Top":"Oldest on top","Slightly sensitive":"Slightly sensitive","Moderately sensitive":"Moderately sensitive","Very sensitive":"Very sensitive","Handheld Only":"Handheld only","Handheld + Screen Off":"Handheld + screen off",Always:"Always","Live (Home Assistant)":"Live (Home Assistant)","Clear Night":"Clear night","Sunny / Clear Day":"Sunny / clear day","Partly Cloudy (Day)":"Partly cloudy (day)","Partly Cloudy (Night)":"Partly cloudy (night)","Cloudy / Overcast (Day)":"Cloudy / overcast (day)","Cloudy / Overcast (Night)":"Cloudy / overcast (night)","Fog / Mist (Day)":"Fog / mist (day)","Fog / Mist (Night)":"Fog / mist (night)","Rainy (Day)":"Rainy (day)","Rainy (Night)":"Rainy (night)","Pouring / Heavy Rain":"Pouring / heavy rain","Snow (Day)":"Snow (day)","Snow (Night)":"Snow (night)","Thunderstorm (Day)":"Thunderstorm (day)","Thunderstorm (Night)":"Thunderstorm (night)",Windy:"Windy",Grid:"Grid",Single:"Single",Carousel:"Carousel",Uncropped:"Uncropped",Fill:"Fill",Auto:"Auto","Low Bandwidth":"Low bandwidth",Snapshots:"Snapshots",Snapshot:"Snapshot","Live Video":"Live video",auto:"Auto (recommended)",allow:"Allow without PIN",require_pin:"Require PIN",block:"Block unlock & disarm"};var rs={system_overview:"view.system_overview",shared_entities:"view.shared_entities",photos:"view.photos",remotes:"view.remotes",system_sync:"view.system_sync",area_tracking:"view.area_tracking",system_tools:"view.system_tools",select_device_prompt:"view.select_device_prompt",discovered_devices:"view.discovered_devices",dashboard:"view.dashboard",display:"view.display",interface:"view.interface",audio_voice:"view.audio_voice",power:"view.power",presence:"view.presence",tools:"view.tools"},ni=[{value:7,label:"7 days"},{value:14,label:"14 days"},{value:30,label:"30 days"},{value:60,label:"60 days"}],si=[{value:"auto",label:"Auto (recommended)"},{value:"allow",label:"Allow without PIN"},{value:"require_pin",label:"Require PIN"},{value:"block",label:"Block unlock & disarm"}],$o=[{value:0,label:"Do not rotate"},{value:5,label:"Every 5 minutes"},{value:15,label:"Every 15 minutes"},{value:30,label:"Every 30 minutes"},{value:60,label:"Every hour"},{value:360,label:"Every 6 hours"},{value:1440,label:"Once a day"}],Yc=/\{([A-Za-z0-9_]+)\}/g;function Zc(e,t){return t?e.replace(Yc,(o,i)=>{let a=t[i];return a==null?o:String(a)}):e}function B(e,t,o){let i=o&&o[e]||$a[e]||e;return Zc(i,t)}function Co(e,t,o){let i=String(e||"").trim();if(!i)return t||"\u2014";let a=o?.[`pref.${i}`];if(a)return a;let n=ns[i];if(n)return n;if(t&&t.trim())return t.trim();let s=i.replace(/_/g," ").trim();return s?s.charAt(0).toUpperCase()+s.slice(1):"\u2014"}function To(e,t,o){let i=String(t??"");if(!i)return"";if(o){let a=e?o[`pref_option.${e}.${i}`]:void 0;if(a)return a;let n=o[`pref_option.${i}`];if(n)return n}return ss[i]??i}function ls(e,t,o,i){let a=String(t||"").trim(),n=e;if(a&&typeof n?.localize=="function"){let c=o?{...o}:void 0;for(let u of[".description",".title",""]){let p=`component.latter.issues.${a}${u}`;try{let d=n.localize(p,c);if(d&&d!==p&&!d.startsWith("component.latter."))return d}catch{}}}if(i)return i;if(!a)return B("issue.generic",{label:"issue"});let s=o?.detail!==void 0?String(o.detail):"";if(a==="missing_mapped_entity")return s?B("issue.missing_mapped_entity_detail",{detail:s}):B("issue.missing_mapped_entity");if(a==="device_crashed")return s==="stall"?B("issue.device_crashed_stall"):s?B("issue.device_crashed_detail",{detail:s}):B("issue.device_crashed");let r=`issue.${a}`;return r in $a?B(r,o):B("issue.generic",{label:a.replace(/_/g," ")})}function xo(e,t,o){let i=String(t||"").trim(),a=i?e?.states?.[i]:void 0,n=e;if(a&&typeof n?.formatEntityState=="function")try{let r=n.formatEntityState(a,o);if(r)return r}catch{}return(o??a?.state??"")||"\u2014"}var Xc=64,cs=new Map,ds=new Map,us=new Map;function Ta(e,t,o){if(e.size>=Xc){let i=e.keys().next().value;i!==void 0&&e.delete(i)}return e.set(t,o),o}function gt(e){return e?.locale}function Ao(e){let t=typeof navigator<"u"?navigator.language:"";return String(gt(e)?.language||e?.language||t||"en")}function xa(e){switch(gt(e)?.number_format){case"comma_decimal":return{locale:"en-US",useGrouping:!0};case"decimal_comma":return{locale:"de-DE",useGrouping:!0};case"space_comma":return{locale:"fr-FR",useGrouping:!0};case"none":return{locale:Ao(e),useGrouping:!1};case"system":return{locale:void 0,useGrouping:void 0};default:return{locale:Ao(e),useGrouping:void 0}}}function ri(e,t){let o=`${e||"sys"}|${t.style||"decimal"}|${t.unit||""}|${t.maximumFractionDigits??""}|${String(t.useGrouping??"")}`,i=cs.get(o);return i||Ta(cs,o,new Intl.NumberFormat(e,t))}function Jc(e){let t=ds.get(e);return t||Ta(ds,e,new Intl.RelativeTimeFormat(e,{numeric:"auto"}))}function Qc(e){switch(gt(e)?.date_format){case"DMY":return"en-GB";case"MDY":return"en-US";case"YMD":return"sv-SE";case"system":return;default:return Ao(e)}}function ed(e){let t=gt(e)?.time_format;if(t==="am_pm")return!0;if(t==="24")return!1}function $e(e){let t=gt(e)?.time_format;if(t==="24")return"24-Hour";if(t==="am_pm")return"12-Hour (AM/PM)";try{let o=gt(e)?.language||e?.language||void 0;if(new Intl.DateTimeFormat(o,{hour:"numeric"}).resolvedOptions().hour12===!1)return"24-Hour"}catch{}return"12-Hour (AM/PM)"}function ps(e,t){let o=String(e??"").trim(),i=/^(\d{1,2}):(\d{2})$/.exec(o);if(!i)return o||"\u2014";let a=Number(i[1]),n=Number(i[2]);if(!Number.isFinite(a)||!Number.isFinite(n)||a<0||a>23||n<0||n>59)return o;let s=String(n).padStart(2,"0");return t?`${String(a).padStart(2,"0")}:${s}`:`${a%12===0?12:a%12}:${s} ${a>=12?"PM":"AM"}`}function Aa(e,t){let o=Number(e);if(!Number.isFinite(o))return"\u2014";let i=(Math.round(o)%24+24)%24;return t?`${String(i).padStart(2,"0")}:00`:`${i%12===0?12:i%12}:00 ${i>=12?"PM":"AM"}`}function td(e,t){let o=`${e||"sys"}|${t.timeZone||"local"}|${String(t.hour12??"auto")}`,i=us.get(o);return i||Ta(us,o,new Intl.DateTimeFormat(e,t))}function ms(e){let t=String(gt(e)?.first_weekday||"language").toLowerCase();if(t==="monday")return"Monday";if(t==="sunday")return"Sunday";try{let o=new Intl.Locale(Ao(e));if((o.getWeekInfo?.()?.firstDay??o.weekInfo?.firstDay)===1)return"Monday"}catch{}return"Sunday"}function A(e,t,o=1){if(e==null||e==="")return"\u2014";let i=Number(e);if(!Number.isFinite(i))return String(e);try{let{locale:a,useGrouping:n}=xa(t);return ri(a,{maximumFractionDigits:o,useGrouping:n}).format(i)}catch{return String(i)}}function li(e,t){if(e==null||e==="")return"\u2014";let o=Number(e);if(!Number.isFinite(o))return String(e);try{let{locale:i,useGrouping:a}=xa(t);return ri(i,{style:"percent",maximumFractionDigits:0,useGrouping:a}).format(o/100)}catch{return`${Math.round(o)}%`}}function zt(e,t,o){let i=t?.config?.unit_system?.length==="mi",{locale:a,useGrouping:n}=xa(t);if(i){let r=o!=null&&Number.isFinite(Number(o)),c=e!=null&&Number.isFinite(Number(e));if(!r&&!c)return"\u2014";let u=r?Number(o):Number(e)*3.28084;try{return ri(a,{style:"unit",unit:"foot",maximumFractionDigits:1,useGrouping:n}).format(u)}catch{return`${u.toFixed(1)} ft`}}if(e==null||!Number.isFinite(Number(e)))return"\u2014";let s=Number(e);try{return ri(a,{style:"unit",unit:"meter",maximumFractionDigits:1,useGrouping:n}).format(s)}catch{return`${s.toFixed(1)} m`}}function gs(e,t){if(e==null||!Number.isFinite(Number(e)))return"\u2014";let o=Math.max(0,Math.round(Number(e)));try{let i=Jc(Ao(t));return o<60?i.format(-o,"second"):o<3600?i.format(-Math.round(o/60),"minute"):o<86400?i.format(-Math.round(o/3600),"hour"):i.format(-Math.round(o/86400),"day")}catch{return`${o}s ago`}}function ci(e,t){if(e==null||e==="")return"";let o=typeof e=="number"?new Date(e<1e12?e*1e3:e):new Date(e);if(Number.isNaN(o.getTime()))return String(e);let a=gt(t)?.time_zone==="server"&&!!t?.config?.time_zone,n={year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",second:"2-digit"},s=ed(t);s!==void 0&&(n.hour12=s),a&&t?.config?.time_zone&&(n.timeZone=t.config.time_zone);try{return td(Qc(t),n).format(o)}catch{return o.toISOString()}}function od(e,t){if(!e)return e;let o=e.toLowerCase(),i=ka[o];return i||(/^[a-z]+[A-Z]/.test(e)||/^[A-Z0-9]{2,}$/.test(e)?e:t?e.charAt(0).toUpperCase()+e.slice(1):e)}function te(e){let t=String(e||"").trim();return t?t.split(/\s+/).filter(Boolean).map((i,a)=>{let n=/^([([{"']*)(.*?)([)\]}"':,.?]*)$/.exec(i),s=n?.[1]??"",r=n?.[2]??i,c=n?.[3]??"";if(!r||s==="("&&c===")"&&/^(ms|s|m|h|d|dB|dBm|Hz|kHz|MHz|V|mV|A|mA|W|%|°C|°F)$/.test(r))return i;let u=r.toLowerCase(),p=ka[u];if(p)return`${s}${p}${c}`;let d=r.split("-").map((m,g)=>od(m,a===0&&g===0)).join("-");return`${s}${d}${c}`}).join(" "):"\u2014"}function di(e,t){let o=String(e.kind||e.key||"");return ls(t,o,e.detail?{detail:e.detail}:void 0)}function ui(e){if(e==null||!Number.isFinite(Number(e)))return 0;let t=Math.max(-95,Math.min(-35,Number(e)));return Math.round((t+95)/60*100)}function ue(e){let t=String(e||"").trim();if(t.length!==7||t.charCodeAt(0)!==35)return!1;for(let o=1;o<7;o+=1){let i=t.charCodeAt(o),a=i>=48&&i<=57,n=i>=65&&i<=70,s=i>=97&&i<=102;if(!a&&!n&&!s)return!1}return!0}function Ca(e){return Math.max(0,Math.min(255,Math.round(e))).toString(16).padStart(2,"0").toUpperCase()}function _s(e,t,o){return"#"+Ca(e)+Ca(t)+Ca(o)}function Ea(e,t,o){let i=o*t,a=i*(1-Math.abs(e/60%2-1)),n=o-i,s=0,r=0,c=0;return e<60?[s,r,c]=[i,a,0]:e<120?[s,r,c]=[a,i,0]:e<180?[s,r,c]=[0,i,a]:e<240?[s,r,c]=[0,a,i]:e<300?[s,r,c]=[a,0,i]:[s,r,c]=[i,0,a],[Math.round((s+n)*255),Math.round((r+n)*255),Math.round((c+n)*255)]}function hs(e,t,o){let[i,a,n]=Ea(e,t,o);return _s(i,a,n)}function Eo(e){if(e&&typeof getComputedStyle=="function"){let t=getComputedStyle(e).getPropertyValue("--primary-color").trim();if(ue(t))return t.toUpperCase()}return _s(0,154,199)}async function Ia(e,t){if(!e)return!1;try{if(typeof navigator<"u"&&typeof navigator.clipboard?.writeText=="function")return await navigator.clipboard.writeText(e),!0}catch{}if(typeof document>"u")return!1;try{let o=(t&&"querySelector"in t?t:null)??document.activeElement?.shadowRoot??document.querySelector("latter-studio")?.shadowRoot??null,i=o&&"activeElement"in o?o.activeElement:document.activeElement,a=o?.querySelector("dialog[open]")??o??document.body,n=document.createElement("textarea");n.className="offscreen",n.setAttribute("aria-hidden","true"),n.tabIndex=-1,n.readOnly=!0,n.value=e,a.appendChild(n),n.focus({preventScroll:!0}),n.select();let s=typeof document.execCommand=="function"&&document.execCommand("copy");return a.removeChild(n),i?.focus?.({preventScroll:!0}),!!s}catch{return!1}}function pi(e,t){let o=new Blob([JSON.stringify(t,null,2)],{type:"application/json"}),i=URL.createObjectURL(o),a=document.createElement("a");a.href=i,a.download=e,document.body.appendChild(a),a.click(),document.body.removeChild(a),setTimeout(()=>URL.revokeObjectURL(i),1e3)}function _t(e,t=!1){e&&(t?globalThis.history.replaceState(null,"",e):globalThis.history.pushState(null,"",e),globalThis.dispatchEvent(new Event("location-changed",{bubbles:!0,composed:!0})))}function vs(e,t){let o=String(e??"");if(t<=0||!o)return"";if(typeof TextEncoder>"u")return o.slice(0,t);let i=new TextEncoder;if(i.encode(o).length<=t)return o;let a="";for(let n of o){if(i.encode(a+n).length>t)break;a+=n}return a}function Kt(e){if(e.currentScope!=="system"){let t=e.entity.getPref("time_format")?.value??e.state?.config?.time_format,o=t!=null?String(t).trim():"";if(o)return o.startsWith("24")}return $e(e.hass).startsWith("24")}function id(e){let t=2166136261;for(let i=0;i<e.length;i+=1)t^=e.charCodeAt(i),t=Math.imul(t,16777619)>>>0;let o=e.toLowerCase().replace(/[^a-z0-9]+/g,"-").replace(/^-+|-+$/g,"").slice(0,28);return o?`${o}-${t.toString(36)}`:`z${t.toString(36)}`}function Wt(e){return e.hasDescription?e.descId?e.descId:e.forId?`${e.forId}-desc`:e.id?`${e.id}-desc`:`row-desc-${id(e.label||"setting")}`:""}var Pa=class extends je{constructor(t){if(super(t),t.type!==Ae.ELEMENT)throw new Error("autoWireDescribedBy() must be used as an element directive")}render(t){return v}update(t,[o]){if(o&&t.element){let i=t.element,a=()=>{let n=i.querySelector("input:not([type='hidden']), select, textarea, [role='combobox']");n&&!n.hasAttribute("aria-describedby")&&n.setAttribute("aria-describedby",o)};a(),queueMicrotask(a)}return ye}},bs=ct(Pa);function Ne(e,t,o="None"){let i=String(t||""),a=e||[],n=!i||a.some(r=>r.id===i),s=[l`<option value="" .selected=${S(i==="")}>${o}</option>`];i&&!n&&s.push(l`<option value=${i} .selected=${S(!0)}>${i} (missing)</option>`);for(let r of a)s.push(l`<option value=${r.id} .selected=${S(r.id===i)}>${r.name||r.id}</option>`);return s}function we(e){return l`<svg viewBox="0 0 24 24" aria-hidden="true"><path d=${e}></path></svg>`}function Se(e,t){return l`<button
    type="button"
    aria-label=${e}
    @click=${t}
    class="btn-icon danger"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9 3v1H4v2h1v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6h1V4h-5V3H9m0 5h2v9H9V8m4 0h2v9h-2V8Z" />
    </svg>
  </button>`}function jt(e,t,o){let i=e.deviceSortField===t,a=i?e.deviceSortAsc?"ascending":"descending":"none",n=i?e.deviceSortAsc?" \u25B2":" \u25BC":"";return l`<th aria-sort=${a}>
    <button type="button" @click=${()=>{e.deviceSortField===t?e.deviceSortAsc=!e.deviceSortAsc:(e.deviceSortField=t,e.deviceSortAsc=!0),e.host.requestUpdate()}} class="sort-btn">${o}<span aria-hidden="true">${n}</span></button>
  </th>`}var fs=new Map;function ad(e){let t=fs.get(e);return t||(t={open:!1,query:"",activeIndex:0},fs.set(e,t)),t}function nd(e,t){if(!e)return!0;if(e.length>t.length)return!1;let o=0;for(let i=0;i<t.length&&o<e.length;i+=1)t.charCodeAt(i)===e.charCodeAt(o)&&(o+=1);return o===e.length}function sd(e,t,o=80){let i=e||[],a=Math.max(1,o),n=String(t||"").trim().toLowerCase();if(!n)return{items:i.slice(0,a),totalMatches:i.length};let s=n.split(/\s+/).filter(Boolean),r=[];for(let c of i){let u=String(c.id||"").toLowerCase(),p=u.includes(".")?u.split(".",2)[1]??u:u,d=String(c.name||c.id||"").toLowerCase(),m=String(c.area_name||"").toLowerCase(),g=String(c.domain||(u.includes(".")?u.split(".",1)[0]??"":"")).toLowerCase(),_=`${d} ${m} ${u} ${g}`,h=!0,b=!1;for(let f of s)if(!_.includes(f)){if(nd(f,`${d} ${u}`)){b=!0;continue}h=!1;break}if(!h)continue;let y=4;b||(d===n||u===n||p===n?y=0:d.startsWith(n)||p.startsWith(n)||u.startsWith(n)?y=1:d.includes(n)||m.includes(n)?y=2:y=3),r.push({item:c,rank:y,labelLow:d})}return r.sort((c,u)=>c.rank-u.rank||c.labelLow.localeCompare(u.labelLow)||c.item.id.localeCompare(u.item.id)),{items:r.slice(0,a).map(c=>c.item),totalMatches:r.length}}function rd(e){return e==="primary"?"chip chip-primary":e==="success"?"chip chip-success":e==="warning"?"chip chip-warning":e==="error"?"chip chip-error":"chip"}function ys(e){let t=ad(e.id),o=String(e.value??"").trim(),i=e.options||[],a=e.maxResults??80,n=o?i.find(E=>E.id===o):void 0,s=o?n?n.name||n.id:B("common.missing_suffix",{id:o},e.overlay):"",{items:r,totalMatches:c}=sd(i,t.open?t.query:"",a),u=r.length>0?Math.max(0,Math.min(r.length-1,t.activeIndex)):-1,p=`${e.id}-listbox`,d=E=>`${e.id}-opt-${E}`,m=t.open&&u>=0?d(u):"",g=E=>{if(e.onUiChange?.(),e.host?.requestUpdate(),!e.onUiChange&&!e.host&&E){let N=typeof E.getRootNode=="function"?E.getRootNode():null;(N&&"host"in N?N.host:null)?.requestUpdate?.()}},_=(E,N)=>{!E||N<0||requestAnimationFrame(()=>{E.closest(".combobox")?.querySelector(`#${CSS.escape(d(N))}`)?.scrollIntoView?.({block:"nearest"})})},h=(E,N)=>{t.open=!1,t.query="",t.activeIndex=0,E!==o&&e.onChange(E),g(N)},b=E=>{if(e.disabled||t.open)return;t.open=!0,t.query="";let N=o?r.findIndex($=>$.id===o):-1;t.activeIndex=N>=0?N:0,g(E)},y=E=>{let N=E.currentTarget;t.open=!0,t.query=N.value,t.activeIndex=0,g(N)},f=E=>{let N=E.currentTarget;if(E.key==="ArrowDown"){if(E.preventDefault(),!t.open){b(N);return}if(r.length>0){let $=(u+1)%r.length;t.activeIndex=$,g(N),_(N,$)}return}if(E.key==="ArrowUp"){if(E.preventDefault(),!t.open){t.open=!0,t.query="",t.activeIndex=Math.max(0,r.length-1),g(N);return}if(r.length>0){let $=(u-1+r.length)%r.length;t.activeIndex=$,g(N),_(N,$)}return}if(t.open&&E.key==="Home"&&r.length>0){E.preventDefault(),t.activeIndex=0,g(N),_(N,0);return}if(t.open&&E.key==="End"&&r.length>0){E.preventDefault();let $=r.length-1;t.activeIndex=$,g(N),_(N,$);return}if(E.key==="Enter"&&!E.isComposing&&E.keyCode!==229){if(t.open){E.preventDefault(),E.stopPropagation();let $=u>=0?r[u]:void 0;$&&h($.id,N)}return}E.key==="Escape"&&t.open&&(E.preventDefault(),E.stopPropagation(),t.open=!1,t.query="",N.value=s,g(N))},k=E=>{let N=E.currentTarget,$=E.relatedTarget;if(!($&&N.contains($))&&t.open){t.open=!1,t.query="";let P=N.querySelector("input[role='combobox']");P&&(P.value=s),g(N)}},w=e.allowClear!==!1&&!!o&&!e.disabled,M=e.placeholder||(o?s:e.emptyOptionLabel||B("combobox.placeholder",void 0,e.overlay));return l`<div @focusout=${k} class="combobox">
    <div class="combobox-input-wrap">
      <input
        type="text"
        id=${e.id}
        role="combobox"
        autocomplete="off"
        spellcheck="false"
        aria-autocomplete="list"
        aria-expanded=${t.open?"true":"false"}
        aria-controls=${p}
        aria-activedescendant=${m||v}
        aria-label=${e.ariaLabel||v}
        aria-describedby=${e.ariaDescribedBy||v}
        placeholder=${M}
        ?disabled=${!!e.disabled}
        .value=${t.open?V(t.query):S(s)}
        @focus=${E=>b(E.currentTarget)}
        @click=${E=>b(E.currentTarget)}
        @input=${y}
        @keydown=${f}
      />
      ${w?l`<button
            type="button"
            aria-label=${B("combobox.clear",void 0,e.overlay)}
            @pointerdown=${E=>{E.preventDefault(),h("",E.currentTarget)}}
            @click=${E=>h("",E.currentTarget)}
            class="combobox-clear"
          >
            ×
          </button>`:v}
    </div>
    <ul
      id=${p}
      role="listbox"
      aria-label=${e.ariaLabel||B("combobox.placeholder",void 0,e.overlay)}
      class="combobox-listbox${t.open?"":" hidden"}"
    >
      ${r.length===0?l`<li role="presentation" class="combobox-empty">
            ${B("combobox.no_matches",void 0,e.overlay)}
          </li>`:ge(r,E=>E.id,(E,N)=>{let $=E.domain||(E.id.includes(".")?E.id.split(".",1)[0]??"":""),P=E.id===o,H=N===u;return l`<li
                id=${d(N)}
                role="option"
                aria-selected=${P?"true":"false"}
                @pointerenter=${C=>{t.activeIndex!==N&&(t.activeIndex=N,g(C.currentTarget))}}
                @pointerdown=${C=>{C.preventDefault(),h(E.id,C.currentTarget)}}
                @click=${C=>h(E.id,C.currentTarget)}
                class="combobox-option${H?" active":""}"
              >
                <div class="combobox-option-main">
                  <span class="combobox-option-title">${E.name||E.id}</span>
                  <span class="combobox-option-id">${E.id}</span>
                </div>
                <span class="combobox-option-chips">
                  ${E.area_name?l`<span class="chip">${E.area_name}</span>`:v}
                  ${$?l`<span class="chip">${$}</span>`:v}
                  ${E.state_label?l`<span class=${rd(E.state_tone)}>${E.state_label}</span>`:v}
                </span>
              </li>`})}
      ${c>r.length?l`<li role="presentation" class="combobox-footer">
            ${B("combobox.showing_top",{shown:r.length,total:c},e.overlay)}
          </li>`:v}
    </ul>
  </div>`}function ws(e,t){if(e){if(!t){if(e.open)try{e.close()}catch{e.removeAttribute("open")}return}if(!e.open)try{e.showModal()}catch{e.setAttribute("open","")}}}function Ss(e){let t=`${e.id}-title`,o=`${e.id}-desc`,i=e.danger!==!1,a=e.blastRadiusCount,n=e.blastRadiusLabel||(a!=null&&a>0?a===1?B("confirm.blast_radius_one",void 0,e.overlay):B("confirm.blast_radius_many",{count:a},e.overlay):""),s=!!e.busy,r=c=>{c.target===c.currentTarget&&!s&&e.onCancel()};return l`<dialog
    id=${e.id}
    aria-labelledby=${t}
    aria-describedby=${o}
    @cancel=${c=>{c.preventDefault(),s||e.onCancel()}}
    @click=${r}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id=${t} class="dialog-title">${e.title}</h3>
        ${n?l`<span class="chip ${i?"chip-warning":"chip-primary"} confirm-blast-badge">
              ${n}
            </span>`:v}
      </div>
      ${e.extraBody&&e.extraBody!==v?e.extraBody:v}
      <p id=${o} class="dialog-text">${e.consequence}</p>
      <div class="dialog-actions${e.onDownloadBackupFirst?" with-secondary":""}">
        ${e.onDownloadBackupFirst?l`<button
              type="button"
              ?disabled=${s}
              @click=${e.onDownloadBackupFirst}
              class="btn btn-text btn-compact"
            >
              ${e.downloadBackupLabel||B("action.download_backup_first",void 0,e.overlay)}
            </button>`:v}
        <div class="dialog-actions-end">
          <button
            type="button"
            ?disabled=${s}
            @click=${e.onCancel}
            class="btn btn-secondary"
          >
            ${e.cancelLabel||B("action.cancel",void 0,e.overlay)}
          </button>
          <button
            type="button"
            id=${e.confirmButtonId||v}
            ?disabled=${!!(e.busy||e.confirmDisabled)}
            @click=${e.onConfirm}
            class="btn ${i?"btn-danger-filled":"btn-primary"}"
          >
            ${e.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  </dialog>`}function U(e){let t=e.heading??l`<h3 class="card-title">${e.title||""}</h3>`,o=e.subtitle||e.headerActions&&e.headerActions!==v?l`<div class="card-heading">
            ${t}
            ${e.subtitle?l`<p class="card-subtitle">${e.subtitle}</p>`:v}
          </div>
          ${e.headerActions&&e.headerActions!==v?l`<div class="card-header-actions">${e.headerActions}</div>`:v}`:t,i=e.contentClass?`card-content ${e.contentClass}`:"card-content";return l`<div id=${e.id||v} class="card${e.danger?" danger":""}${e.handoffActive?" handoff-active":""}">
    <div class="card-header">${o}</div>
    <div class=${i}>${e.body}</div>
    ${e.footerActions&&e.footerActions!==v?l`<div class="card-actions">${e.footerActions}</div>`:v}
  </div>`}function R(e){let t=!!(e.description&&e.description!==v),o=Wt({descId:e.descId,forId:e.forId,id:e.id,label:e.label,hasDescription:t}),i=e.labelHtml??(e.forId?l`<label for=${e.forId} class="row-label">${e.label||""}</label>`:l`<span class="row-label">${e.label||""}</span>`);return l`<div id=${e.id||v} class="settings-row${e.stacked?" stacked":""}">
    <div class="settings-row-text">
      ${i}
      ${t?l`<p id=${o} class="row-description">${e.description}</p>`:v}
    </div>
    <div class="settings-row-control" ${o?bs(o):v}>
      ${e.control}
    </div>
  </div>`}function se(e){let t=String(e.value??""),o=Wt({descId:e.descId,forId:e.id,id:e.rowId,label:e.label,hasDescription:!!(e.description&&e.description!==v)});return R({id:e.rowId,label:e.label,forId:e.id,description:e.description,descId:o||void 0,control:l`<select
      id=${e.id||v}
      aria-label=${e.id?v:e.ariaLabel||e.label}
      aria-describedby=${o||v}
      ?disabled=${!!e.disabled}
      .value=${S(t)}
      @change=${i=>e.onChange(i.currentTarget.value)}
    >
      ${e.rawOptions?e.rawOptions.map(i=>l`<option value=${i.value} .selected=${S(i.value===t)}>${i.label}</option>`):Ne(e.choices,t,e.emptyOptionLabel)}
    </select>`})}function j(e){let t=Wt({descId:e.descId,forId:e.id,id:e.rowId,label:e.label,hasDescription:!!(e.description&&e.description!==v)});return R({id:e.rowId,label:e.label,forId:e.id,description:e.description,descId:t||void 0,control:l`<input
      type="checkbox"
      id=${e.id||v}
      role="switch"
      aria-label=${e.id?v:e.ariaLabel||e.label}
      aria-describedby=${t||v}
      ?disabled=${!!e.disabled}
      .checked=${S(e.checked)}
      @change=${o=>e.onChange(o.currentTarget.checked)}
      class="switch"
    />`})}function Yt(e){let t=e.step??1,o=e.maximumFractionDigits??(Number.isInteger(t)?0:1),i=e.unit===":00",a=e.is24h??$e(e.hass).startsWith("24"),n=!i&&e.unit?e.unit==="%"?"%":` ${e.unit}`:"",s=p=>i?Aa(p,a):`${A(p,e.hass,o)}${n}`,r=s(e.value),c=p=>{let d=p.currentTarget,m=Number(d.value);if(!Number.isFinite(m))return;let g=s(m);d.setAttribute("aria-valuetext",g);let _=d.previousElementSibling;_&&_.classList.contains("kv-value")&&(_.textContent=g),e.onInput?.(m)},u=p=>{let d=Number(p.currentTarget.value);Number.isFinite(d)&&e.onCommit(d)};return l`<span class="kv-value">${r}</span>
    <input
      type="range"
      id=${e.id||v}
      aria-label=${e.ariaLabel}
      aria-describedby=${e.ariaDescribedBy||v}
      aria-valuetext=${r}
      min=${String(e.min)}
      max=${String(e.max)}
      step=${String(t)}
      ?disabled=${!!e.disabled}
      .value=${S(String(e.value))}
      @input=${c}
      @change=${u}
    />`}function Zt(e){let t=Wt({descId:e.descId,forId:e.id,id:e.rowId,label:e.label,hasDescription:!!(e.description&&e.description!==v)});return R({id:e.rowId,label:e.label,forId:e.id,description:e.description,descId:t||void 0,control:Yt({...e,ariaLabel:e.ariaLabel||e.label,ariaDescribedBy:t||e.ariaDescribedBy})})}function Ma(e){let t=e.is24h??$e(e.hass).startsWith("24"),o=(Math.round(e.value)%24+24)%24,i=e.mixed?"__mixed__":String(o);return l`<select
    id=${e.id||v}
    aria-label=${e.ariaLabel}
    aria-describedby=${e.ariaDescribedBy||v}
    ?disabled=${!!e.disabled}
    .value=${S(i)}
    @change=${a=>{let n=a.currentTarget.value;if(n==="__mixed__")return;let s=Number(n);Number.isFinite(s)&&e.onCommit((Math.round(s)%24+24)%24)}}
  >
    ${e.mixed?l`<option value="__mixed__" .selected=${S(!0)} disabled>
          ${e.mixedLabel||B("batch.mixed_badge")}
        </option>`:v}
    ${Array.from({length:24},(a,n)=>{let s=String(n);return l`<option value=${s} .selected=${S(!e.mixed&&n===o)}>
        ${Aa(n,t)}
      </option>`})}
  </select>`}function mi(e){let t=Wt({descId:e.descId,forId:e.id,id:e.rowId,label:e.label,hasDescription:!!(e.description&&e.description!==v)});return R({id:e.rowId,label:e.label,forId:e.id,description:e.description,descId:t||void 0,control:Ma({...e,ariaLabel:e.ariaLabel||e.label,ariaDescribedBy:t||e.ariaDescribedBy})})}var De=null,Da=new Map;function $s(e,t,o,i,a,n){let s=B("common.reordered_status",{item:t,position:o+1,total:i},a);Da.set(e,s);let r=n?.closest("[data-sortable-list]")?.querySelector("[data-sortable-live]");r&&(r.textContent=s)}function ks(e){if(e)for(let t of e.querySelectorAll(".dragging, .drag-over-before, .drag-over-after"))t.classList.remove("dragging","drag-over-before","drag-over-after")}function ld(e,t,o,i){let a=o?t+1:t;return a>e&&(a-=1),Math.max(0,Math.min(i-1,a))}function Cs(e){let t=a=>{if(a.button!==0||e.total<=1)return;let n=a.currentTarget,s=n.closest("[data-sortable-index]"),r=n.closest("[data-sortable-list]");if(!(!s||!r)){a.preventDefault();try{n.setPointerCapture(a.pointerId)}catch{}De={listId:e.listId,pointerId:a.pointerId,orientation:e.orientation,fromIndex:e.idx,overIndex:e.idx,insertAfter:!1},ks(r),s.classList.add("dragging")}},o=a=>{if(!De||De.listId!==e.listId||De.pointerId!==a.pointerId)return;let s=a.currentTarget.closest("[data-sortable-list]");if(!s)return;let r=Array.from(s.querySelectorAll(":scope > [data-sortable-index]"));if(!r.length)return;let c=e.orientation==="horizontal"&&typeof getComputedStyle=="function"&&getComputedStyle(s).direction==="rtl",u=null,p=De.fromIndex,d=1/0,m=!1;for(let g of r){let _=Number(g.dataset.sortableIndex);if(!Number.isFinite(_))continue;let h=g.getBoundingClientRect();if(!(!h.width&&!h.height))if(e.orientation==="vertical"){let b=h.top+h.height/2,y=Math.abs(a.clientY-b);y<d&&(d=y,u=g,p=_,m=a.clientY>b)}else{let b=h.left+h.width/2,y=h.top+h.height/2,f=Math.hypot(a.clientX-b,(a.clientY-y)*1.5);f<d&&(d=f,u=g,p=_,m=c?a.clientX<b:a.clientX>b)}}De.overIndex=p,De.insertAfter=m;for(let g of r)g.classList.remove("drag-over-before","drag-over-after");u&&p!==De.fromIndex&&u.classList.add(m?"drag-over-after":"drag-over-before")},i=(a,n)=>{if(!De||De.listId!==e.listId||De.pointerId!==a.pointerId)return;let s=De;De=null;let r=a.currentTarget,c=r.closest("[data-sortable-list]");try{typeof r.hasPointerCapture=="function"&&r.hasPointerCapture(a.pointerId)&&r.releasePointerCapture(a.pointerId)}catch{}if(ks(c),n)return;let u=ld(s.fromIndex,s.overIndex,s.insertAfter,e.total);u!==s.fromIndex&&(e.onReorder(s.fromIndex,u),$s(e.listId,e.itemLabel,u,e.total,e.overlay,r))};return{onPointerDown:t,onPointerMove:o,onPointerUp:a=>i(a,!1),onPointerCancel:a=>i(a,!0)}}function gi(e){let t=typeof e.btnEl.getRootNode=="function"?e.btnEl.getRootNode():document;e.onReorder(e.fromIndex,e.toIndex),$s(e.listId,e.itemLabel,e.toIndex,e.total,e.overlay,e.btnEl),requestAnimationFrame(()=>{if(!t||typeof t.querySelector!="function")return;let o=t.querySelector(`[data-sortable-list="${CSS.escape(e.listId)}"]`);if(!o)return;let i=o.querySelector(`[data-sortable-key="${CSS.escape(e.itemKey)}"]`);if(!i)return;let a=i.querySelector(`button[data-move-dir="${e.preferredDir}"]:not(:disabled)`);if(a){a.focus({preventScroll:!0});return}i.querySelector("button[data-move-dir]:not(:disabled), button:not(:disabled)")?.focus({preventScroll:!0})})}function Fe(e){let t=e.items.length,o=Da.get(e.id)||"";if(t===0)return l`<div id=${e.id} data-sortable-list=${e.id} class="sortable-list">
      ${typeof e.emptyState=="string"?l`<p class="empty-state">${e.emptyState}</p>`:e.emptyState||v}
      <span data-sortable-live role="status" aria-live="polite" class="sr-only">${o}</span>
    </div>`;let i=new Map,a=e.items.map((n,s)=>{let r=String(e.getKey(n,s)),c=i.get(r)??0;return i.set(r,c+1),c===0?r:`${r}__dup_${c}`});return l`<div
    id=${e.id}
    data-sortable-list=${e.id}
    role="group"
    aria-label=${e.ariaLabel||v}
    class="sortable-list"
  >
    ${ge(e.items,(n,s)=>a[s]??String(s),(n,s)=>{let r=a[s]??String(s),c=e.getLabel(n,s),u=e.canMoveItem?e.canMoveItem(n,s):!0,p=typeof e.rowClass=="function"?e.rowClass(n,s):e.rowClass||"",d=Cs({listId:e.id,orientation:"vertical",idx:s,total:t,itemLabel:c,overlay:e.overlay,onReorder:e.onReorder}),m=u&&t>1?l`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                title=${B("action.drag_reorder",{item:c},e.overlay)}
                @pointerdown=${d.onPointerDown}
                @pointermove=${d.onPointerMove}
                @pointerup=${d.onPointerUp}
                @pointercancel=${d.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`:v,g=l`<div class="sortable-row-actions">
          ${u&&t>1?l`<button
                  type="button"
                  data-move-dir="prev"
                  aria-label=${B("action.move_up",{item:c},e.overlay)}
                  ?disabled=${s===0}
                  @click=${_=>gi({btnEl:_.currentTarget,listId:e.id,itemKey:r,itemLabel:c,preferredDir:"prev",fromIndex:s,toIndex:s-1,total:t,overlay:e.overlay,onReorder:e.onReorder})}
                  class="btn-icon"
                >
                  ↑
                </button>
                <button
                  type="button"
                  data-move-dir="next"
                  aria-label=${B("action.move_down",{item:c},e.overlay)}
                  ?disabled=${s===t-1}
                  @click=${_=>gi({btnEl:_.currentTarget,listId:e.id,itemKey:r,itemLabel:c,preferredDir:"next",fromIndex:s,toIndex:s+1,total:t,overlay:e.overlay,onReorder:e.onReorder})}
                  class="btn-icon"
                >
                  ↓
                </button>`:v}
          ${e.renderActions?e.renderActions(n,s):v}
        </div>`;return e.renderHeader?l`<div
            data-sortable-key=${r}
            data-sortable-index=${String(s)}
            class="sortable-row sortable-row-stacked${p?` ${p}`:""}"
          >
            <div class="sortable-row-head">
              ${m}
              <div class="sortable-row-title">${e.renderHeader(n,s)}</div>
              ${g}
            </div>
            <div class="sortable-row-content">${e.renderContent(n,s)}</div>
          </div>`:l`<div
          data-sortable-key=${r}
          data-sortable-index=${String(s)}
          class="sortable-row${p?` ${p}`:""}"
        >
          ${m}
          <div class="sortable-row-content">${e.renderContent(n,s)}</div>
          ${g}
        </div>`})}
    <span data-sortable-live role="status" aria-live="polite" class="sr-only">${o}</span>
  </div>`}function Ve(e){let t=e.items.filter(r=>r.enabled),o=e.items.filter(r=>!r.enabled),i=t.length,a=e.onReorder,n=!!(a&&i>1),s=Da.get(e.id)||"";return l`<div
    id=${e.id}
    data-sortable-list=${e.id}
    role="group"
    aria-label=${e.ariaLabel||v}
    class="pill-list"
  >
    ${ge(t,r=>r.token,(r,c)=>{let u=a?Cs({listId:e.id,orientation:"horizontal",idx:c,total:i,itemLabel:r.label,overlay:e.overlay,onReorder:a}):null;return l`<span
          data-sortable-key=${r.token}
          data-sortable-index=${n?String(c):v}
          class="pill enabled"
        >
          ${n&&u?l`<button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                title=${B("action.drag_reorder",{item:r.label},e.overlay)}
                @pointerdown=${u.onPointerDown}
                @pointermove=${u.onPointerMove}
                @pointerup=${u.onPointerUp}
                @pointercancel=${u.onPointerCancel}
                class="drag-handle"
              >
                ≡
              </button>`:v}
          ${n&&a?l`<button
                type="button"
                data-move-dir="prev"
                aria-label=${B("action.move_earlier",{item:r.label},e.overlay)}
                ?disabled=${c===0}
                @click=${p=>gi({btnEl:p.currentTarget,listId:e.id,itemKey:r.token,itemLabel:r.label,preferredDir:"prev",fromIndex:c,toIndex:c-1,total:i,overlay:e.overlay,onReorder:a})}
                class="pill-move"
              >
                ‹
              </button>`:v}
          <button
            type="button"
            aria-pressed="true"
            ?disabled=${!!r.disabled}
            @click=${()=>e.onToggle(r.token,!1)}
            class="pill-toggle"
          >
            ${r.label}
          </button>
          ${n&&a?l`<button
                type="button"
                data-move-dir="next"
                aria-label=${B("action.move_later",{item:r.label},e.overlay)}
                ?disabled=${c===i-1}
                @click=${p=>gi({btnEl:p.currentTarget,listId:e.id,itemKey:r.token,itemLabel:r.label,preferredDir:"next",fromIndex:c,toIndex:c+1,total:i,overlay:e.overlay,onReorder:a})}
                class="pill-move"
              >
                ›
              </button>`:v}
        </span>`})}
    ${ge(o,r=>`off:${r.token}`,r=>l`<span class="pill">
        <button
          type="button"
          aria-pressed="false"
          ?disabled=${!!r.disabled}
          @click=${()=>e.onToggle(r.token,!0)}
          class="pill-toggle"
        >
          ${r.label}
        </button>
      </span>`)}
    <span data-sortable-live role="status" aria-live="polite" class="sr-only">${s}</span>
  </div>`}function Io(e){if(!e.items.length)return l`<div id=${e.id} class="stack">
      <p class="empty-state">${e.emptyStateText}</p>
    </div>`;let t=(o,i,a=!0)=>l`<div
    class="stacked-field list-row-grow"
  >
    ${a&&e.slotLabel?l`<span class="field-label">${e.slotLabel(i)}</span>`:v}
    <select
      aria-label=${e.selectAriaLabel}
      .value=${S(o)}
      @change=${n=>e.onChange(i,n.currentTarget.value)}
    >
      ${Ne(e.choices,o,e.emptyOptionLabel)}
    </select>
    ${e.slotMeta?e.slotMeta(o,i):v}
  </div>`;return e.onReorder?Fe({id:e.id,items:e.items,getKey:o=>o?`ent:${o}`:"empty",getLabel:(o,i)=>e.slotLabel?e.slotLabel(i):o||`${e.selectAriaLabel} ${i+1}`,onReorder:e.onReorder,renderHeader:e.stacked?(o,i)=>e.slotLabel?l`<span class="field-label">${e.slotLabel(i)}</span>`:v:void 0,renderContent:(o,i)=>t(o,i,!e.stacked),renderActions:(o,i)=>l`
        ${e.extraActions?e.extraActions(o,i):v}
        ${Se(e.removeAriaLabel,()=>e.onRemove(i))}
      `}):l`<div id=${e.id} class="stack">
    ${e.items.map((o,i)=>l`<div class="list-row">
        ${t(o,i)}
        ${e.extraActions?e.extraActions(o,i):v}
        ${Se(e.removeAriaLabel,()=>e.onRemove(i))}
      </div>`)}
  </div>`}function La(e){let o=e.state?.locale_strings;return o&&typeof o=="object"?o:null}function xs(e,t){let o=La(e),i=t.pref_key||"",a=i?Co(i,te(t.name||t.entity_id),o):te(t.name||t.entity_id),n=t.domain,s=String(t.state??""),r=!i&&(s==="unavailable"||s==="unknown");if(n==="switch"){let u=s==="on",p=d=>{let m=d.currentTarget.checked;i?e.entity.stageDeviceSetting(i,m):e.entity.espAction(t.entity_id,m?"turn_on":"turn_off",m?"on":"off")};return R({label:a,control:l`<input
        type="checkbox"
        role="switch"
        aria-label=${a}
        ?disabled=${r}
        .checked=${S(u)}
        @change=${p}
        class="switch"
      />`})}if(n==="select"){let u=t.options||[],p=d=>{let m=d.currentTarget.value;i?e.entity.stageDeviceSetting(i,m):e.entity.espSelect(t.entity_id,m)};return R({label:a,control:l`<select aria-label=${a} ?disabled=${r} .value=${S(s)} @change=${p}>
        ${u.map(d=>l`<option value=${d} .selected=${S(d===s)}>
              ${To(i,d,o)}
            </option>`)}
      </select>`})}if(n==="number"){let u=t.min??0,p=t.max??100,d=t.step??1,m=Number.isFinite(Number(s))?Number(s):u,g=_=>{i?e.entity.stageDeviceSetting(i,_):e.entity.espNumber(t.entity_id,_)};return p-u<=250&&t.mode!=="box"?R({label:a,control:Yt({ariaLabel:a,value:m,min:u,max:p,step:d,unit:t.unit,is24h:Kt(e),disabled:r,hass:e.hass,onCommit:g})}):R({label:a,control:l`<input
          type="number"
          aria-label=${a}
          min=${String(u)}
          max=${String(p)}
          step=${String(d)}
          ?disabled=${r}
          .value=${V(String(m))}
          @change=${_=>{let h=Number(_.currentTarget.value);Number.isFinite(h)&&g(h)}}
        />
        ${t.unit?l`<span class="help-text">${t.unit}</span>`:v}`})}if(n==="button"){let u=s==="unavailable",p=a.toLowerCase().includes("restart")?B("sync.restarting_device",void 0,o):B("sync.triggered_action",{label:a},o);return R({label:a,control:l`<button
        type="button"
        ?disabled=${u}
        @click=${()=>{t.device_command?e.entity.runDeviceAction(t.device_command,p):e.entity.espAction(t.entity_id,"press",void 0,p)}}
        class="btn btn-secondary btn-compact"
      >
        ${B("action.run",void 0,o)}
      </button>`})}if(n==="update"){let u=s==="on";return R({label:a,control:l`<span class="chip ${u?"chip-warning":""}">${u?B("status.update",void 0,o):B("status.up_to_date",void 0,o)}</span>
        ${u?l`<button
              type="button"
              @click=${()=>{e.entity.espAction(t.entity_id,"install")}}
              class="btn btn-primary btn-compact"
            >
              ${B("action.install",void 0,o)}
            </button>`:v}`})}let c=r?"\u2014":t.unit&&Number.isFinite(Number(s))?`${A(Number(s),e.hass)} ${t.unit}`:s||"\u2014";return l`<div class="kv-row">
    <span>${a}</span>
    <strong>${c}</strong>
  </div>`}function pe(e,t,o){let i=La(e),a=o||Co(t.key,t.label||te(t.key),i),n=t.domain,s=t.value;if(n==="switch"){let r=!!s,c=u=>{let p=u.currentTarget.checked;e.entity.stageDeviceSetting(t.key,p)};return R({label:a,control:l`<input
        type="checkbox"
        role="switch"
        aria-label=${a}
        .checked=${S(r)}
        @change=${c}
        class="switch"
      />`})}if(n==="select"){let r=t.options||[],c=String(s??""),u=p=>{let d=p.currentTarget.value;e.entity.stageDeviceSetting(t.key,d)};return R({label:a,control:l`<select aria-label=${a} .value=${S(c)} @change=${u}>
        ${r.map(p=>l`<option value=${p} .selected=${S(p===c)}>
              ${To(t.key,p,i)}
            </option>`)}
      </select>`})}if(n==="number"){let r=t.min??0,c=t.max??100,u=t.step??1,p=Number.isFinite(Number(s))?Number(s):r;return t.unit===":00"?mi({label:a,ariaLabel:a,value:p,is24h:Kt(e),hass:e.hass,onCommit:d=>e.entity.stageDeviceSetting(t.key,d)}):c-r<=250?R({label:a,control:Yt({ariaLabel:a,value:p,min:r,max:c,step:u,unit:t.unit,is24h:Kt(e),hass:e.hass,onCommit:d=>e.entity.stageDeviceSetting(t.key,d)})}):R({label:a,control:l`<input
          type="number"
          aria-label=${a}
          min=${String(r)}
          max=${String(c)}
          step=${String(u)}
          .value=${V(String(p))}
          @change=${d=>{let m=Number(d.currentTarget.value);Number.isFinite(m)&&e.entity.stageDeviceSetting(t.key,m)}}
        />
        ${t.unit?l`<span class="help-text">${t.unit}</span>`:v}`})}return v}var Ts={find_my:0,voice:1,screensaver:2,hibernate:3,restart:4,other:5};function Ra(e){let t=(e.name||"").toLowerCase(),o=e.entity_id.includes(".")?(e.entity_id.split(".",2)[1]??e.entity_id).toLowerCase():e.entity_id.toLowerCase();return e.device_class==="identify"||t.includes("find my")||o.endsWith("find_my_device")||o.includes("_find_my")?"find_my":e.device_class==="restart"||t.includes("restart")||o.endsWith("_restart_device")||o.endsWith("_restart")?"restart":t.includes("screensaver")||o.includes("screensaver")?"screensaver":t.includes("hibernate")||o.includes("hibernate")?"hibernate":t.includes("voice")||t.includes("assist")||o.includes("trigger_voice")||o.includes("trigger_va")?"voice":"other"}function cd(e){return e==="find_my"?l`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a10 10 0 1 0 10 10A10 10 0 0 0 12 2m0 18a8 8 0 1 1 8-8 8 8 0 0 1-8 8m0-14a6 6 0 1 0 6 6 6 6 0 0 0-6-6m0 10a4 4 0 1 1 4-4 4 4 0 0 1-4 4m0-6a2 2 0 1 0 2 2 2 2 0 0 0-2-2Z"
      />
    </svg>`:e==="voice"?l`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3m7 9c0 3.53-2.61 6.44-6 6.93V21h-2v-3.07c-3.39-.49-6-3.4-6-6.93h2a5 5 0 0 0 10 0h2Z"
      />
    </svg>`:e==="screensaver"?l`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M20 3H4a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h6v2H7v2h10v-2h-3v-2h6a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2m0 13H4V5h16v11M11.2 6.8a3.8 3.8 0 1 0 2.4 6 3.5 3.5 0 0 1-2.4-6m5.3-.6.65 1.65 1.65.65-1.65.65-.65 1.65-.65-1.65-1.65-.65 1.65-.65.65-1.65Z"
      />
    </svg>`:e==="hibernate"?l`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M16.56 5.44l-1.45 1.45A5.969 5.969 0 0 1 18 12a6 6 0 0 1-6 6 6 6 0 0 1-6-6c0-2.17 1.16-4.06 2.88-5.12L7.44 5.44A7.961 7.961 0 0 0 4 12a8 8 0 0 0 8 8 8 8 0 0 0 8-8c0-2.72-1.36-5.12-3.44-6.56M13 3h-2v10h2V3Z"
      />
    </svg>`:e==="restart"?l`<svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M17.65 6.35A7.958 7.958 0 0 0 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0 1 12 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35Z"
      />
    </svg>`:l`<svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M7 2h10l-3.5 7H17l-7 13v-8H6l1-12Z" />
  </svg>`}function dd(e){return[...e].sort((t,o)=>{let i=Ts[Ra(t)],a=Ts[Ra(o)];return i!==a?i-a:`${t.name||""} ${t.entity_id}`.toLowerCase().localeCompare(`${o.name||""} ${o.entity_id}`.toLowerCase())})}function As(e,t,o=!1){if(!t.length)return v;let i=La(e),a=dd(t);return l`<div
    class="quick-action-grid"
    role="group"
    aria-label=${B("card.quick_actions",void 0,i)}
  >
    ${a.map(n=>{let s=Ra(n),r=te(n.name||n.entity_id),c=o||String(n.state??"")==="unavailable",u=s==="restart"?B("sync.restarting_device",void 0,i):s==="hibernate"?B("sync.hibernating_device",void 0,i):B("sync.triggered_action",{label:r},i),p=()=>{n.device_command?e.entity.runDeviceAction(n.device_command,u):e.entity.espAction(n.entity_id,"press",void 0,u)};return l`<button
        type="button"
        data-entity-id=${n.entity_id}
        ?disabled=${c}
        @click=${p}
        class="btn btn-secondary quick-action-btn"
      >
        ${cd(s)}
        <span>${r}</span>
      </button>`})}
  </div>`}function Pe(e){let t=e.state;if((t?.config||{}).kind==="ble_tag")return v;if(((t?.system_devices||[]).find(s=>s.subentry_id===e.activeSubentryId)||(t?.system_devices||[]).find(s=>s.is_current))?.is_online!==!1)return v;let a=!!t?.live?.is_ble_sleep_expected,n=a?"offline.device_sleeping_title":"offline.device_banner_title";return l`<div
    id="device-offline-banner"
    role="region"
    aria-label=${e.t(n)}
    class="alert offline-banner"
  >
    <div class="offline-banner-body">
      <strong>${e.t(n)}</strong>
      <span>${e.t("offline.device_banner_body")}</span>
    </div>
    <span class="chip">
      ${a?e.t("status.sleeping"):e.t("status.offline")}
    </span>
  </div>`}function Ce(e,t){if(t.pref_key||t.domain==="switch"||t.domain==="number"||t.domain==="button"||t.domain==="update")return xs(e,t);let o=te(t.name||t.entity_id),i=String(t.state??""),a=i==="unavailable"||i==="unknown";if(t.domain==="select"){let s=t.options||[],r=c=>{e.entity.espSelect(t.entity_id,c.currentTarget.value)};return R({label:o,control:l`<select aria-label=${o} ?disabled=${a} .value=${S(i)} @change=${r}>
        ${s.map(c=>l`<option value=${c} .selected=${S(c===i)}>
              ${xo(e.hass,t.entity_id,c)}
            </option>`)}
      </select>`})}let n=a?e.t("common.unknown"):t.unit&&Number.isFinite(Number(i))?`${A(Number(i),e.hass)} ${t.unit}`:xo(e.hass,t.entity_id,i);return l`<div class="kv-row">
    <span>${o}</span>
    <strong>${n}</strong>
  </div>`}var Es=[],Is={};var Xe={light:[{action:"toggle",label:"Toggle"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],switch:[{action:"toggle",label:"Toggle"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],input_boolean:[{action:"toggle",label:"Toggle"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],fan:[{action:"toggle",label:"Toggle"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],cover:[{action:"toggle",label:"Toggle"},{action:"open_cover",label:"Open"},{action:"close_cover",label:"Close"},{action:"stop_cover",label:"Stop"}],valve:[{action:"toggle",label:"Toggle"},{action:"open_valve",label:"Open"},{action:"close_valve",label:"Close"},{action:"stop_valve",label:"Stop"}],scene:[{action:"turn_on",label:"Activate"}],script:[{action:"turn_on",label:"Run"},{action:"turn_off",label:"Stop"}],automation:[{action:"trigger",label:"Trigger"},{action:"toggle",label:"Toggle enable"},{action:"turn_on",label:"Enable"},{action:"turn_off",label:"Disable"}],button:[{action:"press",label:"Press"}],input_button:[{action:"press",label:"Press"}],lock:[{action:"lock",label:"Lock"},{action:"unlock",label:"Unlock"},{action:"open",label:"Unlatch"}],alarm_control_panel:[{action:"disarm",label:"Disarm"},{action:"arm_home",label:"Arm home"},{action:"arm_away",label:"Arm away"},{action:"arm_night",label:"Arm night"},{action:"arm_vacation",label:"Arm vacation"}],vacuum:[{action:"start",label:"Start"},{action:"pause",label:"Pause"},{action:"return_to_base",label:"Return to base"},{action:"stop",label:"Stop"},{action:"clean_spot",label:"Spot clean"},{action:"locate",label:"Locate"}],lawn_mower:[{action:"start_mowing",label:"Start mowing"},{action:"pause",label:"Pause"},{action:"dock",label:"Dock"}],media_player:[{action:"media_play_pause",label:"Play / pause"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"},{action:"media_next_track",label:"Next track"}],climate:[{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],humidifier:[{action:"toggle",label:"Toggle"},{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],siren:[{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],water_heater:[{action:"turn_on",label:"Turn on"},{action:"turn_off",label:"Turn off"}],select:[{action:"select_next",label:"Next option"},{action:"select_previous",label:"Previous option"}],input_select:[{action:"select_next",label:"Next option"},{action:"select_previous",label:"Previous option"}]},Ps={alarm_control_panel:"Security alarm",automation:"Automations",button:"Buttons",climate:"Climate",cover:"Covers & blinds",fan:"Fans",humidifier:"Humidifiers",input_boolean:"Input booleans",input_button:"Input buttons",input_select:"Input selects",lawn_mower:"Lawn mowers",light:"Lights",lock:"Locks",media_player:"Media players",scene:"Scenes",script:"Scripts",select:"Selects",siren:"Sirens",switch:"Switches",vacuum:"Vacuums",valve:"Valves",water_heater:"Water heaters"};function bi(e,t){let i=(Xe[e]||[]).find(a=>a.action===t);return i?i.label:t}var nt={"app:pinned":"mdi:pin","app:music":"mdi:music","music:speakers":"mdi:speaker-multiple","music:library":"mdi:music-box","music:favorites":"mdi:heart","music:playlists":"mdi:playlist-music","music:queue":"mdi:playlist-play","music:album_tracks":"mdi:album","music:lyrics":"mdi:script-text","music:info":"mdi:information","app:home_hub":"mdi:home","home_hub:alarm":"mdi:shield-home","home_hub:intercom":"mdi:bullhorn","home_hub:thermostat":"mdi:thermostat","home_hub:entry":"mdi:lock","home_hub:vacuum":"mdi:robot-vacuum","app:cameras":"mdi:cctv","cameras:grid":"mdi:view-grid","cameras:single":"mdi:video","cameras:carousel":"mdi:view-carousel","cameras:settings":"mdi:cog","app:area":"mdi:sofa","area:picker":"mdi:floor-plan","area:scene":"mdi:shimmer","area:light":"mdi:lightbulb","area:cover":"mdi:blinds-horizontal","area:climate":"mdi:thermometer","area:fan":"mdi:fan","area:switch":"mdi:toggle-switch","area:media":"mdi:television-speaker","area:all":"mdi:view-grid","app:remote":"mdi:remote-tv","remote:devices":"mdi:remote","app:weather":"mdi:weather-partly-cloudy","weather:current":"mdi:weather-partly-cloudy","weather:forecast":"mdi:calendar-week","weather:sun":"mdi:white-balance-sunny","weather:moon":"mdi:moon-waning-crescent","app:time":"mdi:clock","time:clock":"mdi:clock","time:timers":"mdi:timer-sand","time:alarms":"mdi:alarm","time:stopwatch":"mdi:timer","app:clock":"mdi:clock","app:calendar":"mdi:calendar","calendar:overview":"mdi:calendar-text","calendar:day":"mdi:calendar-today","calendar:week":"mdi:calendar-week","calendar:month":"mdi:calendar-month","app:tools":"mdi:view-grid","tools:stopwatch":"mdi:timer","tools:level":"mdi:spirit-level","tools:flashlight":"mdi:flashlight","tools:calculator":"mdi:calculator-variant","tools:dice":"mdi:dice-5","tools:coin_flip":"mdi:alpha-c-circle","app:games":"mdi:controller","games:marbles":"mdi:billiards","games:archery":"mdi:bullseye-arrow","games:bricks":"mdi:wall","games:chomp":"mdi:pac-man","games:2048":"mdi:numeric-2-box-multiple","games:memory":"mdi:cards","settings:root":"mdi:cog","settings:display":"mdi:brightness-6","settings:sleep":"mdi:power-sleep","settings:sound":"mdi:volume-high","settings:voice":"mdi:microphone","settings:music":"mdi:music-box","settings:home":"mdi:home","settings:actions":"mdi:gesture-tap-button","settings:update":"mdi:cellphone-arrow-down","settings:info":"mdi:information"},ud=/^mdi:[a-z0-9]+(?:-[a-z0-9]+)*$/,pd=/^[a-z0-9]+(?:-[a-z0-9]+)*$/;function st(e){let t=String(e??"").trim().toLowerCase().replace(/_/g,"-");return t?(t.startsWith("mdi-")?t=`mdi:${t.slice(4)}`:!t.startsWith("mdi:")&&pd.test(t)&&(t=`mdi:${t}`),ud.test(t)?t:""):""}var Pt=["mdi:pin","mdi:pin-outline","mdi:bell-ring","mdi:bell","mdi:bell-alert","mdi:bullhorn","mdi:lifebuoy","mdi:alert-circle","mdi:hand-wave","mdi:baby-carriage","mdi:baby-bottle-outline","mdi:baby-face-outline","mdi:cradle-outline","mdi:human-male-female-child","mdi:account-heart","mdi:heart","mdi:medical-bag","mdi:phone-in-talk","mdi:message-alert","mdi:flash","mdi:lightning-bolt","mdi:star","mdi:shimmer","mdi:magic-staff","mdi:check-circle","mdi:lightbulb","mdi:lightbulb-on","mdi:lightbulb-outline","mdi:lightbulb-group","mdi:lamp","mdi:desk-lamp","mdi:floor-lamp","mdi:ceiling-light","mdi:chandelier","mdi:coach-lamp","mdi:outdoor-lamp","mdi:wall-sconce","mdi:led-strip-variant","mdi:string-lights","mdi:track-light","mdi:lava-lamp","mdi:candle","mdi:fireplace","mdi:brightness-6","mdi:creation","mdi:palette","mdi:toggle-switch","mdi:toggle-switch-off-outline","mdi:power","mdi:power-plug","mdi:power-socket-us","mdi:power-socket-eu","mdi:light-switch","mdi:battery-charging","mdi:solar-power","mdi:ev-station","mdi:car-electric","mdi:blinds-horizontal","mdi:blinds-horizontal-closed","mdi:blinds-open","mdi:blinds-vertical","mdi:curtains","mdi:curtains-closed","mdi:roller-shade","mdi:roller-shade-closed","mdi:window-shutter","mdi:window-shutter-open","mdi:window-open-variant","mdi:window-closed-variant","mdi:garage","mdi:garage-open","mdi:garage-variant","mdi:garage-open-variant","mdi:gate","mdi:gate-open","mdi:door","mdi:door-open","mdi:door-closed","mdi:door-sliding","mdi:awning-outline","mdi:lock","mdi:lock-open","mdi:lock-smart","mdi:key-variant","mdi:shield-home","mdi:shield-lock","mdi:shield-check","mdi:shield-moon","mdi:shield-airplane","mdi:security","mdi:alarm-light","mdi:cctv","mdi:video","mdi:webcam","mdi:doorbell-video","mdi:motion-sensor","mdi:smoke-detector-variant","mdi:thermostat","mdi:thermometer","mdi:fire","mdi:snowflake","mdi:sun-snowflake-variant","mdi:fan","mdi:ceiling-fan","mdi:air-purifier","mdi:air-humidifier","mdi:water-percent","mdi:water-boiler","mdi:water","mdi:water-pump","mdi:pipe-valve","mdi:sprinkler-variant","mdi:faucet","mdi:radiator","mdi:hvac","mdi:robot-vacuum","mdi:robot-mower","mdi:washing-machine","mdi:tumble-dryer","mdi:dishwasher","mdi:fridge-outline","mdi:stove","mdi:coffee-maker","mdi:kettle-steam","mdi:music","mdi:music-note","mdi:playlist-music","mdi:playlist-play","mdi:radio","mdi:podcast","mdi:speaker","mdi:speaker-multiple","mdi:cast-audio","mdi:television","mdi:television-speaker","mdi:remote","mdi:remote-tv","mdi:play-pause","mdi:play","mdi:pause","mdi:skip-next","mdi:volume-high","mdi:volume-mute","mdi:movie-open","mdi:controller","mdi:gamepad-variant","mdi:headphones","mdi:script-text-play","mdi:script-text","mdi:robot","mdi:gesture-tap-button","mdi:cog","mdi:cog-play","mdi:autorenew","mdi:timer-play","mdi:weather-night","mdi:sleep","mdi:bed","mdi:coffee","mdi:silverware-fork-knife","mdi:party-popper","mdi:airplane","mdi:home-export-outline","mdi:home-import-outline","mdi:briefcase","mdi:laptop","mdi:book-open-variant","mdi:meditation","mdi:dumbbell","mdi:home","mdi:home-outline","mdi:sofa","mdi:bed-king-outline","mdi:desk","mdi:countertop-outline","mdi:shower-head","mdi:bathtub-outline","mdi:stairs","mdi:balcony","mdi:flower","mdi:tree","mdi:pine-tree","mdi:pool","mdi:grill","mdi:car","mdi:bicycle","mdi:dog","mdi:cat","mdi:paw","mdi:weather-sunny","mdi:weather-partly-cloudy","mdi:weather-cloudy","mdi:weather-rainy","mdi:weather-pouring","mdi:weather-snowy","mdi:weather-lightning","mdi:weather-windy","mdi:white-balance-sunny","mdi:moon-waning-crescent","mdi:moon-full","mdi:clock-outline","mdi:alarm","mdi:timer-sand","mdi:timer-outline","mdi:calendar","mdi:calculator-variant","mdi:flashlight","mdi:spirit-level","mdi:dice-5","mdi:compass-outline","mdi:map-marker","mdi:apps","mdi:view-grid","mdi:view-grid-outline","mdi:form-select"],md="./latter-studio-mdi.js?v=5b5dad0000fc8b54",ht=Es,_i=Is,Mo=null,hi=null,vi=null,Do=null,Oa=null,Ba=null,Po=null;function gd(){return Oa===null&&(Oa=new Set(Pt)),Oa}function _d(e,t){if(t==="all")return!0;let o=e.endsWith("-outline");return t==="outline"?o:!o}function hd(e){let t=[],o="";for(let i of e)for(let a of i.split("|")){if(!a)continue;let n=a[0];if(!n)continue;let s=parseInt(n,36),r=o.slice(0,s)+a.slice(1);o=r,t.push(`mdi:${r}`)}return t}function Ms(){return ht.length>0}function vd(e,t){!Array.isArray(e)||e.length===0||(ht=e,t&&typeof t=="object"&&(_i=t),Mo=null,hi=null,vi=null,Do=null)}function Ds(){return ht.length>0?Promise.resolve():Po||(Po=import(md).then(e=>{e&&Array.isArray(e.PACKED_MDI_CHUNKS)&&vd(e.PACKED_MDI_CHUNKS,e.MDI_SEARCH_SYNONYMS)}).catch(e=>{throw Po=null,e}),Po)}function fi(){return ht.length===0?Pt:(Mo!==null||(Mo=hd(ht)),Mo)}function Rs(){return hi===null&&(hi=new Set(fi())),hi}function bd(){if(vi!==null)return vi;let e=fi(),t=0;for(let i of e)i.endsWith("-outline")&&(t+=1);let o={solid:e.length-t,outline:t};return ht.length>0&&(vi=o),o}function fd(e){if(Do!==null&&Do.length>=e)return Do.slice(0,e);let t=new Set,o=[],i=a=>{t.has(a)||(t.add(a),o.push(a))};for(let a of Pt)a.endsWith("-outline")&&i(a);if(ht.length>0){let a=Rs();for(let n of Pt)if(!n.endsWith("-outline")){let s=`${n}-outline`;a.has(s)&&i(s)}if(o.length<e){for(let n of fi())if(n.endsWith("-outline")&&(i(n),o.length>=e))break}Do=o}return o.slice(0,e)}function Ro(e){let t=st(e);return t?ht.length===0?(Ba===null&&(Ba=new Set([...Pt,...Object.values(nt)])),Ba.has(t)):Rs().has(t):!1}function Na(e,t){return e===t||e.startsWith(`${t}-`)||e.endsWith(`-${t}`)?!0:e.includes(`-${t}-`)}function Ha(e){let t=_i[e];if(t&&t.length>0)return t;if(e.length>4&&e.endsWith("es")){let o=e.slice(0,-2),i=_i[o];if(i&&i.length>0)return i}if(e.length>3&&e.endsWith("s")){let o=e.slice(0,-1),i=_i[o];if(i&&i.length>0)return i}return[]}function Ls(e,t=120,o="all"){let a=String(e||"").trim().toLowerCase().replace(/^mdi[-:]/,"").replace(/[_\s]+/g,"-").split("-").filter(Boolean);if(a.length===0){if(o==="all")return{items:Pt.slice(0,t),totalMatches:7447};let _=bd();return o==="solid"?{items:Pt.filter(b=>!b.endsWith("-outline")).slice(0,t),totalMatches:_.solid}:{items:fd(t),totalMatches:_.outline}}let n=a[0]??"",s=a.join("-"),r=a.join(""),c=new Set;for(let _ of Ha(s))c.add(_);if(r!==s)for(let _ of Ha(r))c.add(_);let u=a.map(_=>Ha(_)),p=c.size>0||u.some(_=>_.length>0),d=a.length===1&&s.length<=2&&c.size>0,m=gd(),g=[];for(let _ of fi()){if(!_d(_,o))continue;let h=_.slice(4),b=!0;for(let k of a)if(!h.includes(k)){b=!1;break}if(b){let k=3;h===s?k=0:d?h.startsWith(`${s}-`)?k=1:Na(h,s)?k=2:k=5:h.startsWith(s)?k=1:n&&(h.includes(`-${n}`)||h.startsWith(n))&&(k=2),g.push({slug:_,rank:k,subRank:0});continue}if(!p)continue;let y=!1,f=!1;if(c.size>0){for(let k of c)if(Na(h,k)&&(y=!0,h===k||h===`${k}-outline`)){f=!0;break}}if(!y&&a.length>1){let k=!0,w=!1;for(let M=0;M<a.length;M+=1){let E=a[M]??"";if(h.includes(E))continue;let $=(u[M]??[]).find(P=>Na(h,P));if(!$){k=!1;break}w=!0,(h===$||h===`${$}-outline`)&&(f=!0)}k&&w&&(y=!0)}if(y){let k=(f?0:2)+(m.has(_)?0:1);g.push({slug:_,rank:4,subRank:k})}}return g.sort((_,h)=>_.rank-h.rank||_.subRank-h.subRank||_.slug.localeCompare(h.slug)),{items:g.slice(0,t).map(_=>_.slug),totalMatches:g.length}}var Fa=15e3,Lo=6e4;function Oo(e){if(!e||typeof e!="object")return!1;let t=String(e.code||"");return t==="studio_rev_mismatch"||t==="version_mismatch"}function Xt(e){return!e||typeof e!="object"?!1:String(e.code||"")==="conflict"}function G(e,t="Action failed"){return e?typeof e=="string"?e:typeof e=="object"&&"message"in e&&e.message?String(e.message):t:t}function Os(e,t){let o=null,i=new Promise((a,n)=>{o=setTimeout(()=>{n(new Error("Request timed out \u2014 check your Home Assistant connection and try again."))},t)});return Promise.race([e,i]).finally(()=>{o!==null&&clearTimeout(o)})}var yi=class{hassRef=null;onRevMismatch;constructor(t){this.onRevMismatch=t}setHass(t){this.hassRef=t}get hass(){return this.hassRef}requireHass(){if(!this.hassRef)throw new Error("Home Assistant connection is not ready");return this.hassRef}async callWS(t,o=Fa){let i=this.requireHass();try{return await Os(i.callWS(t),o)}catch(a){throw Oo(a)&&this.onRevMismatch(),a}}async getState(t){return this.callWS({type:"latter/system/get_state",subentry_id:t.subentryId||null,include_logs:!!t.includeLogs,studio_rev:46})}async subscribe(t,o){let i=this.requireHass();if(!i.connection)throw new Error("Home Assistant WebSocket connection is unavailable");try{let a={type:"latter/system/subscribe",subentry_id:t.subentryId||null,include_logs:!!t.includeLogs,studio_rev:46};return t.surveySubentryId&&(a.survey_subentry_id=t.surveySubentryId),await Os(i.connection.subscribeMessage(o,a),Fa)}catch(a){throw Oo(a)&&this.onRevMismatch(),a}}async runSystemCommand(t,o={},i){if(!bo.has(t))throw new Error(`Unknown System command: ${t}`);let a=t==="check_system_updates"||t==="import_media_photos"?Lo:Fa;return this.callWS({type:"latter/system/command",command:t,subentry_id:i||null,payload:o,studio_rev:46},a)}async browseMediaFolder(t,o){if(!bo.has("browse_media_folder"))throw new Error("browse_media_folder is not registered in Studio protocol contract");let i={};return t!==void 0&&t!==""&&(i.root=t),o!==void 0&&o!==""&&(i.subpath=o),this.callWS({type:"latter/system/command",command:"browse_media_folder",subentry_id:null,payload:i,studio_rev:46})}async mintCameraPreviewUrl(t){if(!bo.has("mint_camera_preview_url"))throw new Error("mint_camera_preview_url is not registered in Studio protocol contract");return this.callWS({type:"latter/system/command",command:"mint_camera_preview_url",subentry_id:null,payload:{camera_entity:t},studio_rev:46})}async runDeviceCommand(t,o,i={}){if(!da.has(o))throw new Error(`Unknown Device command: ${o}`);if(!t)throw new Error("Choose a Device first");return this.callWS({type:"latter/device/command",command:o,subentry_id:t,payload:i,studio_rev:46})}async exportBackup(t,o){if(t==="device"){if(!o)throw new Error("Choose a Device to export");return this.callWS({type:"latter/device/export",subentry_id:o,studio_rev:46})}return this.callWS({type:"latter/system/export",studio_rev:46})}async importBackup(t){if(t.scope==="device"){if(!t.targetSubentryId)throw new Error("Choose the Device to restore this backup onto");return this.callWS({type:"latter/device/import",subentry_id:t.targetSubentryId,bundle:t.bundle,studio_rev:46},Lo)}return this.callWS({type:"latter/system/import",subentry_id:t.selectedSubentryId||null,bundle:t.bundle,studio_rev:46},Lo)}async resetDevice(t){return this.callWS({type:"latter/device/reset",subentry_id:t.subentryId,device_settings:t.deviceSettings,latter_options:t.latterOptions,studio_rev:46},Lo)}async signHaPath(t,o=300){let i=await this.callWS({type:"auth/sign_path",path:t,expires:o});if(!i||!i.path)throw new Error("Could not sign Home Assistant path");return i.path}async getAccessToken(t=!1){let i=this.requireHass().auth;if(!i)throw new Error("Home Assistant authentication session is not ready");(t||i.expired)&&typeof i.refreshAccessToken=="function"&&await i.refreshAccessToken();let a=i.data?.access_token;if(!a)throw new Error("Home Assistant access token is unavailable");return a}async uploadWallpaperMultipart(t){if(!t.file)throw new Error("Choose an image file first");if(t.file.size>ii)throw new Error("Photo must be 15 MB or smaller");if(t.scope==="device"&&!t.subentryId)throw new Error("Choose a Device before uploading a Device wallpaper");let o="/api/latter/wallpaper/upload",i=new FormData;i.append("file",t.file,t.file.name||"photo.jpg"),i.append("scope",t.scope),t.subentryId&&i.append("subentry_id",t.subentryId),t.name&&t.name.trim()&&i.append("name",t.name.trim()),t.crop&&(i.append("crop_x",String(t.crop.x)),i.append("crop_y",String(t.crop.y)),i.append("crop_zoom",String(t.crop.zoom))),t.collectionId&&t.collectionId.trim()&&i.append("collection_id",t.collectionId.trim());let a=p=>new Promise((d,m)=>{let g=new XMLHttpRequest;g.open("POST",o,!0),g.setRequestHeader("Authorization",`Bearer ${p}`),g.responseType="json",g.timeout=Lo,g.upload&&t.onProgress&&(g.upload.onprogress=_=>{_.lengthComputable&&_.total>0&&t.onProgress?.(Math.min(100,Math.round(_.loaded/_.total*100)))}),g.onload=()=>{let _=g.response&&typeof g.response=="object"?g.response:null;d({status:g.status,body:_})},g.onerror=()=>{m(new Error("Network error while uploading wallpaper"))},g.ontimeout=()=>{m(new Error("Wallpaper upload timed out"))},g.onabort=()=>{m(new Error("Wallpaper upload was canceled"))},g.send(i)}),n=await this.getAccessToken(!1),s=await a(n);s.status===401&&typeof this.hassRef?.auth?.refreshAccessToken=="function"&&(n=await this.getAccessToken(!0),s=await a(n));let{status:r,body:c}=s;if(r>=200&&r<300)return t.onProgress?.(100),{ok:!0,photo_id:c?.photo_id?String(c.photo_id):void 0,filename:c?.filename?String(c.filename):void 0,source_id:c?.source_id?String(c.source_id):void 0,photo:c?.photo&&typeof c.photo=="object"?c.photo:void 0,photo_collections:Array.isArray(c?.photo_collections)?c.photo_collections:void 0,wallpapers:Array.isArray(c?.wallpapers)?c.wallpapers:void 0,system_wallpapers:Array.isArray(c?.system_wallpapers)?c.system_wallpapers:void 0};let u=c?.error?String(c.error):c?.message?String(c.message):`Wallpaper upload failed (HTTP ${r})`;throw new Error(u)}};var rt={x:.5,y:.5,zoom:1};function qe(e,t,o){return!Number.isFinite(e)||e<t?t:e>o?o:e}function vt(e){return{x:qe(Number(e?.x??.5),0,1),y:qe(Number(e?.y??.5),0,1),zoom:qe(Number(e?.zoom??1),1,3)}}function Bs(e,t,o,i,a){let n=Math.max(1,e),s=Math.max(1,t),r=Math.max(1,o),c=Math.max(1,i),u=qe(a.zoom,1,3),p=n/s,d=r/c,m,g;p>d?(g=s,m=s*d):(m=n,g=n/d);let _=Math.min(n,m/u),h=Math.min(s,g/u),b=qe(a.x,0,1)*n,y=qe(a.y,0,1)*s,f=qe(b-_/2,0,Math.max(0,n-_)),k=qe(y-h/2,0,Math.max(0,s-h));return{sx:f,sy:k,sw:_,sh:h}}function Ns(e,t,o,i,a,n,s){if(i<=0||a<=0||n<=0||s<=0)return vt(e);let r=Bs(i,a,n,s,e),c=r.sw/(2*i),u=r.sh/(2*a),p=Math.min(.5,c),d=Math.max(.5,1-c),m=Math.min(.5,u),g=Math.max(.5,1-u),_=(r.sx+r.sw/2)/i,h=(r.sy+r.sh/2)/a,b=qe(_-t/n*(r.sw/i),p,d),y=qe(h-o/s*(r.sh/a),m,g);return{x:Math.round(b*1e3)/1e3,y:Math.round(y*1e3)/1e3,zoom:qe(e.zoom,1,3)}}function Va(e){return e==="widescreen"?{width:320,height:180}:{width:260,height:260}}function wi(e,t,o,i,a){let n=e.getContext("2d");if(!n)return;let s=e.width,r=e.height;if(n.clearRect(0,0,s,r),n.fillStyle="#111111",n.fillRect(0,0,s,r),t&&t.naturalWidth>0&&t.naturalHeight>0){let c=Bs(t.naturalWidth,t.naturalHeight,s,r,o);n.save(),i==="round"&&(n.beginPath(),n.arc(s/2,r/2,Math.min(s,r)/2,0,Math.PI*2),n.clip()),n.drawImage(t,c.sx,c.sy,c.sw,c.sh,0,0,s,r),n.restore()}a?.showGuides!==!1&&(n.save(),i==="square"?(n.strokeStyle="rgba(255, 255, 255, 0.28)",n.lineWidth=1,n.beginPath(),n.moveTo(s/3,0),n.lineTo(s/3,r),n.moveTo(2*s/3,0),n.lineTo(2*s/3,r),n.moveTo(0,r/3),n.lineTo(s,r/3),n.moveTo(0,2*r/3),n.lineTo(s,2*r/3),n.stroke(),n.strokeStyle="rgba(255, 255, 255, 0.65)",n.lineWidth=1.5,n.setLineDash([6,4]),n.beginPath(),n.arc(s/2,r/2,Math.min(s,r)/2-2,0,Math.PI*2),n.stroke()):i==="round"?(n.strokeStyle="rgba(255, 255, 255, 0.72)",n.lineWidth=2,n.beginPath(),n.arc(s/2,r/2,Math.min(s,r)/2-1,0,Math.PI*2),n.stroke()):(n.strokeStyle="rgba(255, 255, 255, 0.28)",n.lineWidth=1,n.beginPath(),n.moveTo(s/3,0),n.lineTo(s/3,r),n.moveTo(2*s/3,0),n.lineTo(2*s/3,r),n.moveTo(0,r/3),n.lineTo(s,r/3),n.moveTo(0,2*r/3),n.lineTo(s,2*r/3),n.stroke()),n.restore())}function me(e,t){let o=e.capability;if(!o||!t)return!0;switch(o){case"round":return t.is_round!==!1;case"imu":return t.has_imu!==!1;case"display_imu":return t.has_display!==!1&&t.has_imu!==!1;case"display":return t.has_display!==!1;case"battery":return t.has_battery!==!1;case"display_battery":return t.has_display!==!1&&t.has_battery!==!1;case"beacon_battery":return t.has_ble_beacon!==!1&&t.has_battery!==!1;case"mic":return t.has_voice!==!1;case"speaker":return t.has_audio!==!1;case"hw_jpeg":return t.hw_jpeg===!0;default:return!0}}var Hs=["calendar_entities","camera_entities","remotes_list","thermostat_entities","lock_entities","garage_entities","vacuum_entities","broadcast_speakers","broadcast_phrases"],Je={camera_entities:10,remotes_list:10,calendar_entities:50,thermostat_entities:8,lock_entities:8,garage_entities:6,vacuum_entities:6,broadcast_speakers:32,broadcast_phrases:12};function qa(e){return e==="calendar_entities"||e==="camera_entities"||e==="remotes_list"||e==="thermostat_entities"||e==="lock_entities"||e==="garage_entities"||e==="vacuum_entities"||e==="broadcast_speakers"||e==="broadcast_phrases"}function Qe(e,t){let o=[];for(let i of e){let a=String(i||"").trim();if(a&&!o.includes(a)&&(o.push(a),o.length>=t))break}return o}function Si(e,t,o,i){let a=Qe(e,o),n=Math.max(0,Math.min(t,o-a.length));if(n===0)return{uiList:a,clampedBlankCount:0};if(i&&i.some(s=>!String(s||"").trim())){let s=[],r=0,c=0;for(let u of i){if(s.length>=o)break;if(!String(u||"").trim())c<n&&(s.push(""),c+=1);else if(r<a.length){let p=a[r];p!==void 0&&s.push(p),r+=1}}for(;r<a.length&&s.length<o;){let u=a[r];u!==void 0&&s.push(u),r+=1}for(;c<n&&s.length<o;)s.push(""),c+=1;return{uiList:s,clampedBlankCount:c}}return{uiList:[...a,...Array(n).fill("")],clampedBlankCount:n}}function Jt(){return{open:!1,files:[],activeIndex:0,collectionId:"",newCollectionOpen:!1,newCollectionName:"",creatingCollection:!1,previewAspect:"square",uploading:!1,currentIndex:0,currentPercent:0,draggingFiles:!1,onComplete:null}}function Qt(){return{open:!1,photoId:"",name:"",crop:{...rt},collections:[],previewAspect:"square",busy:!1}}function eo(){return{open:!1,loading:!1,importing:!1,error:"",roots:[],root:"",subpath:"",parentSubpath:null,folders:[],images:[],selectedPaths:[],collectionId:"",useNewFolderCollection:!1,newCollectionName:"",deduplicate:!0}}function Mt(){return{open:!1,target:"wallpaper",mode:"photos",collectionId:de,selectedIds:[],search:"",filterCollection:de,busy:!1}}function Bo(){return{open:!1,kind:"",title:"",consequence:"",confirmLabel:"",cancelLabel:"",danger:!0,blastRadiusCount:null,blastRadiusLabel:"",busy:!1,onConfirm:null,onDownloadBackupFirst:null}}var Fs=new Set(os),Vs=new Set(is),qs=new Set(as);function Us(e,t){let o=new Set(Fs);for(let i of t)(i.group_tier==="behavior"||i.group_tier==="display"&&e.include_display||i.group_tier==="interface"&&e.include_interface)&&o.add(i.key);if(e.include_display)for(let i of Vs)o.add(i);if(e.include_interface)for(let i of qs)o.add(i);return o}function yd(e,t){return e===t?!0:Array.isArray(e)||e&&typeof e=="object"||Array.isArray(t)||t&&typeof t=="object"?JSON.stringify(e)===JSON.stringify(t):String(e)===String(t)}function wd(e,t){let o={...t};return t.home_screen_enabled===!1&&String(t.start_screen??e.start_screen??"Home")==="Home"&&(o.start_screen="Time App"),o}function Dt(e,t){if(!t||Object.keys(t).length===0)return;let o=e.config||{},i=wd(o,t),a=e.device_groups||[],n=e.device_prefs||[],s=new Set(n.map(u=>u.key)),r=o.is_roaming!==!1;if("device_group"in t){let u=String(t.device_group||"custom").trim()||"custom";if(i.device_group=u,u!=="custom"){let p=a.find(d=>d.id===u);if(p?.device_config){let d=Us(p,n);for(let[m,g]of Object.entries(p.device_config))m in t||g===void 0||g===null||d.has(m)&&((m==="sync_device_area"||m==="area_follow_dwell_s")&&!r||(Fs.has(m)||Vs.has(m)||qs.has(m)||s.has(m))&&(i[m]=g))}}}else{let u=String(o.device_group||"custom").trim()||"custom";if(u!=="custom"){let p=a.find(d=>d.id===u);if(p?.device_config){let d=Us(p,n);for(let[m,g]of Object.entries(i))if(!((m==="sync_device_area"||m==="area_follow_dwell_s")&&!r)&&d.has(m)&&p.device_config[m]!==void 0&&!yd(p.device_config[m],g)){i.device_group="custom";break}}}}if(e.config={...e.config,...i},"device_group"in i&&Array.isArray(e.system_devices)&&e.subentry_id){let u=String(i.device_group||"custom"),p=u==="custom"?"Custom":a.find(d=>d.id===u)?.name||u;e.system_devices=e.system_devices.map(d=>d.subentry_id===e.subentry_id?{...d,device_group:u,device_group_name:p}:d)}e.device_prefs&&(e.device_prefs=e.device_prefs.map(u=>u.key in i?{...u,value:i[u.key]}:u));let c=e?.esphome?.sections;c&&(e.esphome={...e.esphome,sections:c.map(u=>({...u,items:(u.items||[]).map(p=>{if(p.pref_key&&p.pref_key in i){let d=i[p.pref_key],m=p.domain==="switch"?d?"on":"off":String(d??"");return{...p,state:m}}if("volume_step_size"in i&&p.domain==="number"&&p.entity_id.startsWith("media_player.")){let d=Number(i.volume_step_size);if(Number.isFinite(d)&&d>0)return{...p,step:d}}return p})}))})}function No(e,t){let o=Date.now();for(let[a,n]of t.entries())n.expires<=o&&t.delete(a);let i=e?.esphome?.sections;!i||t.size===0||(e.esphome={...e.esphome,sections:i.map(a=>({...a,items:(a.items||[]).map(n=>{let s=t.get(n.entity_id);if(!s)return n;let r=String(n.state??""),c=r!==""&&s.state!==""&&Number.isFinite(Number(r))&&Number.isFinite(Number(s.state))&&Number(r)===Number(s.state);return r===s.state||c?(t.delete(n.entity_id),n):{...n,state:s.state}})}))})}function to(e,t,o){if(!t.system_config)return;let i=!1,a={...t.system_config};for(let n of Hs){let s=e.pendingBlankListSlots[n]||0;if(s<=0)continue;let r=Je[n],c=Array.isArray(a[n])?a[n]:[],{uiList:u,clampedBlankCount:p}=Si(c,s,r,o?.[n]);e.pendingBlankListSlots[n]=p,a[n]=u,i=!0}i&&(t.system_config=a)}function Gs(e,t,o,i){let a=Je[t],n=[...e.state?.system_config?.[t]||[]];if(o<0||o>=n.length)return;let s=Qe(n,a),r=[...n];r[o]=String(i||"").trim();let c=new Set,u=[];for(let m of r){let g=String(m||"").trim();if(g?c.has(g)||(c.add(g),u.push(g)):u.push(""),u.length>=a)break}let p=u.filter(Boolean);e.pendingBlankListSlots[t]=u.length-p.length,s.length!==p.length||s.some((m,g)=>m!==p[g])?(e.entity.stageSystemSetting(t,p),e.state?.system_config&&e.pendingBlankListSlots[t]>0&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:u}},e.host.requestUpdate())):e.state?.system_config&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:u}},e.host.requestUpdate())}function zs(e,t,o="",i=Je[t]){let a=Math.min(i,Je[t]),n=[...e.state?.system_config?.[t]||[]];if(n.length>=a){e.showToast(`Maximum of ${a} entries reached`,!0);return}let s=String(o||"").trim();if(!s){n.push(""),e.pendingBlankListSlots[t]=n.filter(u=>!String(u||"").trim()).length,e.state?.system_config&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:n}}),e.host.requestUpdate();return}let r=Qe([...n,s],a),c=Math.max(0,Math.min(e.pendingBlankListSlots[t]||0,a-r.length));e.pendingBlankListSlots[t]=c,e.entity.stageSystemSetting(t,r),e.state?.system_config&&c>0&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:[...r,...Array(c).fill("")]}},e.host.requestUpdate())}function Ks(e,t,o){let i=Je[t],a=[...e.state?.system_config?.[t]||[]];if(o<0||o>=a.length)return;let[n]=a.splice(o,1),s=!String(n||"").trim();if(e.pendingBlankListSlots[t]=a.filter(c=>!String(c||"").trim()).length,s){e.state?.system_config&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:a}}),e.host.requestUpdate();return}let r=Qe(a,i);if(e.entity.stageSystemSetting(t,r),e.state?.system_config&&e.pendingBlankListSlots[t]>0){let{uiList:c,clampedBlankCount:u}=Si(r,e.pendingBlankListSlots[t],i,a);e.pendingBlankListSlots[t]=u,e.state={...e.state,system_config:{...e.state.system_config,[t]:c}},e.host.requestUpdate()}}function Ga(e,t,o,i){let a=Je[t],n=[...e.state?.system_config?.[t]||[]];if(o<0||o>=n.length||i<0||i>=n.length||o===i)return;let s=Qe(n,a),[r]=n.splice(o,1);if(r===void 0)return;n.splice(i,0,r);let c=Qe(n,a);e.pendingBlankListSlots[t]=n.filter(p=>!String(p||"").trim()).length,s.length!==c.length||s.some((p,d)=>p!==c[d])?(e.entity.stageSystemSetting(t,c),e.state?.system_config&&e.pendingBlankListSlots[t]>0&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:n}},e.host.requestUpdate())):e.state?.system_config&&(e.state={...e.state,system_config:{...e.state.system_config,[t]:n}},e.host.requestUpdate())}function Ws(e){let t=[...e.state?.system_config?.volume_overrides||[]];if(t.length>=10){e.showToast("Maximum of 10 volume overrides reached",!0);return}let o=e.state?.catalog?.ma_speakers||[],i=e.state?.catalog?.volume_targets||e.state?.catalog?.remotes||[];t.push({speaker:o[0]?.id||"",target:i[0]?.id||o[0]?.id||""}),e.entity.stageSystemSetting("volume_overrides",t)}function js(e,t,o,i){let a=(e.state?.system_config?.volume_overrides||[]).map(s=>({...s})),n=a[t];n&&(n[o]=i,e.entity.stageSystemSetting("volume_overrides",a))}function Ys(e,t){let o=[...e.state?.system_config?.volume_overrides||[]];o.splice(t,1),e.entity.stageSystemSetting("volume_overrides",o)}function Zs(e){let t=(e.state?.system_config?.remote_groups||[]).map(i=>({...i,remotes:[...i.remotes||[]]})),o=`group_${Date.now().toString(36)}`;t.push({id:o,name:"New remote group",area_id:"",remotes:[]}),e.entity.stageSystemSetting("remote_groups",t)}function Xs(e,t,o,i){let a=(e.state?.system_config?.remote_groups||[]).map(n=>n.id===t?{...n,[o]:i}:{...n,remotes:[...n.remotes||[]]});e.entity.stageSystemSetting("remote_groups",a)}function Js(e,t,o){let i=(e.state?.system_config?.remote_groups||[]).map(a=>{if(a.id!==t)return{...a,remotes:[...a.remotes||[]]};let n=[...a.remotes||[]],s=n.indexOf(o);return s>=0?n.splice(s,1):n.push(o),{...a,remotes:n}});e.entity.stageSystemSetting("remote_groups",i)}function Qs(e,t){let o=(e.state?.system_config?.remote_groups||[]).filter(i=>i.id!==t);e.entity.stageSystemSetting("remote_groups",o)}function Ho(e){let t=[];for(let o of e.state?.system_config?.broadcast_speakers||[]){let i=String(o||"").trim();i&&!t.includes(i)&&t.push(i)}return t}function ki(e){let t=Ho(e);if(t.length===0)return[];let o=e.state?.config?.broadcast_speaker_entities;if(!Array.isArray(o)||o.length===0)return[...t];let i=[];for(let a of o){let n=String(a||"").trim();n&&t.includes(n)&&!i.includes(n)&&i.push(n)}return i.length>0?i:[...t]}function er(e,t,o){let i=String(t||"").trim(),a=Ho(e);if(!i||!a.includes(i))return;let n=ki(e),r=n.indexOf(i)>=0,c=o!==void 0?!!o:!r;if(c===r)return;let u;if(c)u=[...n,i];else{if(n.length<=1){e.showToast(e.t("common.keep_one_enabled",{noun:"speaker"}),!0);return}u=n.filter(d=>d!==i)}let p=u.length===a.length&&u.every((d,m)=>d===a[m]);e.entity.stageDeviceSetting("broadcast_speaker_entities",p?[]:u)}function tr(e,t,o){let i=Ho(e),a=ki(e);if(t<0||o<0||t>=a.length||o>=a.length||t===o)return;let n=[...a],[s]=n.splice(t,1);if(s===void 0)return;n.splice(o,0,s);let r=n.length===i.length&&n.every((c,u)=>c===i[u]);e.entity.stageDeviceSetting("broadcast_speaker_entities",r?[]:n)}function Uo(e){let t=[];for(let o of e.state?.system_config?.camera_entities||[]){let i=String(o||"").trim();i&&!t.includes(i)&&t.push(i)}return t}function Rt(e){let t=Uo(e);if(t.length===0)return[];let o=e.state?.config?.camera_visible_entities;if(!Array.isArray(o)||o.length===0)return[...t];let i=[];for(let a of o){let n=String(a||"").trim();n&&t.includes(n)&&!i.includes(n)&&i.push(n)}return i.length>0?i:[...t]}function or(e,t,o){let i=String(t||"").trim(),a=Uo(e);if(!i||!a.includes(i))return;let n=Rt(e),r=n.indexOf(i)>=0,c=o!==void 0?!!o:!r;if(c===r)return;let u;if(c)u=[...n,i];else{if(n.length<=1){e.showToast(e.t("common.keep_one_enabled",{noun:"camera"}),!0);return}u=n.filter(d=>d!==i)}let p=u.length===a.length&&u.every((d,m)=>d===a[m]);if(e.entity.stageDeviceSetting("camera_visible_entities",p?[]:u),!c){let d=Array.isArray(e.state?.config?.camera_carousel_entities)?e.state.config.camera_carousel_entities.map(m=>String(m||"").trim()).filter(Boolean):[];if(d.length>0&&d.includes(i)){let m=d.filter(_=>u.includes(_)),g=m.length===u.length&&m.every((_,h)=>_===u[h]);e.entity.stageDeviceSetting("camera_carousel_entities",m.length===0||g?[]:m)}}}function ir(e,t,o){let i=Uo(e),a=Rt(e);if(t<0||o<0||t>=a.length||o>=a.length||t===o)return;let n=[...a],[s]=n.splice(t,1);if(s===void 0)return;n.splice(o,0,s);let r=n.length===i.length&&n.every((c,u)=>c===i[u]);e.entity.stageDeviceSetting("camera_visible_entities",r?[]:n)}function $i(e){let t=Rt(e);if(t.length===0)return[];let o=e.state?.config?.camera_carousel_entities;if(!Array.isArray(o)||o.length===0)return[...t];let i=[];for(let a of o){let n=String(a||"").trim();n&&t.includes(n)&&!i.includes(n)&&i.push(n)}return i.length>0?i:[...t]}function ar(e,t,o){let i=String(t||"").trim(),a=Rt(e);if(!i||!a.includes(i))return;let n=$i(e),r=n.indexOf(i)>=0,c=o!==void 0?!!o:!r;if(c===r)return;let u;if(c)u=[...n,i];else{if(n.length<=1){e.showToast(e.t("common.keep_one_enabled",{noun:"camera"}),!0);return}u=n.filter(d=>d!==i)}let p=u.length===a.length&&u.every((d,m)=>d===a[m]);e.entity.stageDeviceSetting("camera_carousel_entities",p?[]:u)}function nr(e,t,o){let i=Rt(e),a=$i(e);if(t<0||o<0||t>=a.length||o>=a.length||t===o)return;let n=[...a],[s]=n.splice(t,1);if(s===void 0)return;n.splice(o,0,s);let r=n.length===i.length&&n.every((c,u)=>c===i[u]);e.entity.stageDeviceSetting("camera_carousel_entities",r?[]:n)}function Ge(e){return e.kind==="uploaded"||e.kind==="upload"||e.source_kind==="upload"||e.source_kind==="media_import"||!!e.deletable}function lt(e){return e.kind==="dynamic_preset"||e.source_kind==="dynamic_preset"}function Ci(e,t,o=!1){let i=new Set(t.filter(s=>!o||!lt(s)).map(s=>s.id)),a=[],n=new Set;for(let s of e||[]){let r=String(s||"").trim();!r||n.has(r)||!i.has(r)||(n.add(r),a.push(r))}return a}function sr(e){return String(e||"").replace(/^.*[\\/]/,"").replace(/\.[^.]+$/,"").replace(/[_-]+/g," ").trim()||"Photo"}function oo(e,t,o,i){let a=String(o||"").trim().toLowerCase();return e.filter(n=>{if(i?.excludeDynamic&&lt(n))return!1;if(t===Ye){if(Ge(n))return!1}else if(t===Ze){if(!Ge(n))return!1}else if(t===mt){if((n.collections||[]).length>0)return!1}else if(t&&t!==de&&!(n.collections||[]).includes(t))return!1;return!(a&&!`${n.name||""} ${n.id||""} ${n.media_source_path||""}`.toLowerCase().includes(a))})}function Ti(e,t){return!t||t===de?e.t("photos.filter_all"):t===Ye?e.t("photos.filter_defaults"):t===Ze?e.t("photos.filter_my_photos"):t===mt?e.t("photos.filter_uncategorized"):(e.state?.photo_collections||[]).find(i=>i.id===t)?.name||t}function za(e,t,o,i,a,n){let s=n?.excludeDynamic?e.filter(r=>!lt(r)):[...e];if(t==="off")return[];if(t==="single"){let r=s.find(c=>c.id===o);return r?[r]:[]}if(t==="collection")return oo(s,i||de,"",n);if(t==="custom"){let r=new Map(s.map(u=>[u.id,u])),c=[];for(let u of a){let p=r.get(u);p&&!c.includes(p)&&c.push(p)}return c}return[]}function xi(e){if(!(typeof URL>"u"||typeof URL.revokeObjectURL!="function")){for(let t of e)if(t.objectUrl)try{URL.revokeObjectURL(t.objectUrl)}catch{}}}var Sd=0;function rr(e,t){xi(e.photoUploadModal.files);let o=t?.defaultCollectionId??(e.photosFilterCollection.startsWith("col_")?e.photosFilterCollection:"");e.photoUploadModal={...Jt(),open:!0,collectionId:o,onComplete:t?.onComplete??null},e.host.requestUpdate()}function lr(e){e.photoUploadModal.uploading||(xi(e.photoUploadModal.files),e.photoUploadModal=Jt(),e.host.requestUpdate())}function cr(e,t){let o=Array.from(t||[]);if(!o.length)return;let i=[...e.photoUploadModal.files];for(let n of o){if(!n)continue;if(n.size>ii){e.showToast(e.t("photo_upload.file_too_large",{name:n.name||"image"}),!0);continue}let s=`staged_${++Sd}`,r=typeof URL<"u"&&typeof URL.createObjectURL=="function"?URL.createObjectURL(n):"";i.push({id:s,file:n,name:sr(n.name),crop:{...rt},objectUrl:r,width:0,height:0})}let a=e.photoUploadModal.files.length===0&&i.length>0?0:Math.min(e.photoUploadModal.activeIndex,Math.max(0,i.length-1));e.photoUploadModal={...e.photoUploadModal,files:i,activeIndex:a,draggingFiles:!1},e.host.requestUpdate()}function dr(e,t){let o=e.photoUploadModal.files;if(t<0||t>=o.length||e.photoUploadModal.uploading)return;let i=o[t];i&&xi([i]);let a=o.filter((s,r)=>r!==t),n=Math.min(e.photoUploadModal.activeIndex,Math.max(0,a.length-1));e.photoUploadModal={...e.photoUploadModal,files:a,activeIndex:n},e.host.requestUpdate()}async function ur(e){let t=e.photoUploadModal;if(t.uploading||t.creatingCollection||t.files.length===0)return;if(t.newCollectionOpen&&t.newCollectionName.trim()){if(!await Wa(e))return;t=e.photoUploadModal}e.photoUploadModal={...t,uploading:!0,currentIndex:0,currentPercent:0},e.host.requestUpdate();let o=[],i=t.files.length,a=t.collectionId||"",n=t.onComplete;try{for(let s=0;s<i;s+=1){let r=t.files[s];if(!r)continue;e.photoUploadModal={...e.photoUploadModal,currentIndex:s+1,currentPercent:0},e.host.requestUpdate();let c=await e.ws.uploadWallpaperMultipart({scope:"system",file:r.file,name:r.name.trim()||sr(r.file.name),crop:vt(r.crop),collectionId:a||void 0,onProgress:p=>{e.photoUploadModal={...e.photoUploadModal,currentPercent:p},e.host.requestUpdate()}}),u=c.photo_id||c.source_id||c.photo?.id||"";u&&o.push(u),e.state&&c.system_wallpapers&&(e.state={...e.state,system_wallpapers:c.system_wallpapers,photo_collections:c.photo_collections??e.state.photo_collections})}xi(e.photoUploadModal.files),e.photoUploadModal=Jt(),await e.refreshState(),e.showToast(o.length===1?e.t("photo_upload.uploaded_one_toast"):e.t("photo_upload.uploaded_many_toast",{count:o.length})),n&&n(o)}catch(s){e.photoUploadModal={...e.photoUploadModal,uploading:!1},e.host.requestUpdate(),e.showToast(G(s,"Photo upload failed"),!0)}}function pr(e,t){e.photoEditModal={open:!0,photoId:t.id,name:t.name||t.id,crop:vt(t.crop),collections:[...t.collections||[]],previewAspect:"square",busy:!1},e.host.requestUpdate()}function mr(e){e.photoEditModal.busy||(e.photoEditModal=Qt(),e.host.requestUpdate())}async function gr(e){let t=e.photoEditModal;if(!t.open||!t.photoId||t.busy)return;let o=(e.state?.system_wallpapers||[]).find(a=>a.id===t.photoId),i=o?Ge(o):t.photoId.startsWith("photo:");e.photoEditModal={...t,busy:!0},e.host.requestUpdate();try{let a={photo_id:t.photoId,collections:[...t.collections]};if(i){let s=t.name.trim();s&&(a.name=s),a.crop=vt(t.crop)}let n=await e.ws.runSystemCommand("update_photo_metadata",a,e.activeSubentryId||null);e.photoEditModal=Qt(),n?e.ingestPayload(n,!1):e.host.requestUpdate(),e.showToast(e.t("photos.updated_photo_toast"))}catch(a){e.photoEditModal={...e.photoEditModal,busy:!1},e.host.requestUpdate(),e.showToast(G(a,"Could not update photo"),!0)}}async function Ka(e,t){let o=String(t||"").trim();if(!o)return null;try{let i=await e.ws.runSystemCommand("create_photo_collection",{name:o},e.activeSubentryId||null);return e.photosNewCollectionOpen=!1,e.photosNewCollectionName="",i&&e.ingestPayload(i,!1),e.showToast(e.t("photos.created_collection_toast",{name:o})),String(i?.collection?.id||"").trim()||null}catch(i){return e.showToast(G(i,"Could not create collection"),!0),null}}async function Wa(e){let t=e.photoUploadModal,o=t.newCollectionName.trim();if(!t.open||t.uploading||t.creatingCollection||!o)return null;e.photoUploadModal={...t,creatingCollection:!0},e.host.requestUpdate();let i=await Ka(e,o);return i?e.photoUploadModal={...e.photoUploadModal,collectionId:i,newCollectionOpen:!1,newCollectionName:"",creatingCollection:!1}:e.photoUploadModal={...e.photoUploadModal,creatingCollection:!1},e.host.requestUpdate(),i}async function _r(e,t,o){let i=String(t||"").trim(),a=String(o||"").trim();if(!(!i||!a))try{let n=await e.ws.runSystemCommand("rename_photo_collection",{collection_id:i,name:a},e.activeSubentryId||null);e.photosRenamingCollectionId="",e.photosRenamingCollectionName="",n&&e.ingestPayload(n,!1),e.showToast(e.t("photos.renamed_collection_toast",{name:a}))}catch(n){e.showToast(G(n,"Could not rename collection"),!0)}}function hr(e,t,o){let i=String(t||"").trim();i&&e.openConfirm({kind:"delete_collection",title:e.t("confirm.delete_collection.title",{name:o}),consequence:e.t("confirm.delete_collection.body"),confirmLabel:e.t("confirm.delete_collection.confirm"),danger:!0,onConfirm:async()=>{try{let a=await e.ws.runSystemCommand("delete_photo_collection",{collection_id:i},e.activeSubentryId||null);e.photosFilterCollection===i&&(e.photosFilterCollection=de,e.photosPage=1),a&&e.ingestPayload(a,!1),e.showToast(e.t("photos.deleted_collection_toast"))}catch(a){e.showToast(G(a,"Could not delete collection"),!0)}}})}async function ja(e,t){let o=String(t||"").trim();if(o)try{let i=await e.ws.runSystemCommand("delete_photo",{photo_id:o},e.activeSubentryId||null);e.photosSelectedIds.delete(o),e.photoEditModal.open&&e.photoEditModal.photoId===o&&(e.photoEditModal=Qt()),i&&e.ingestPayload(i,!1),e.showToast(e.t("photos.deleted_photo_toast"))}catch(i){e.showToast(G(i,"Could not delete photo"),!0)}}function vr(e,t,o){let i=String(t||"").trim();if(!i)return;let a=String(o||i).trim();e.openConfirm({kind:"delete_photo",title:e.t("confirm.delete_photo.title",{name:a}),consequence:e.t("confirm.delete_photo.body"),confirmLabel:e.t("confirm.delete_photo.confirm"),danger:!0,onConfirm:async()=>{await ja(e,i)}})}async function Ya(e,t){let o=Array.from(e.photosSelectedIds);if(o.length===0)return;let i={photo_ids:o};t.addCollection&&(i.add_collection=t.addCollection),t.removeCollection&&(i.remove_collection=t.removeCollection),t.deletePhotos&&(i.delete=!0);try{let a=await e.ws.runSystemCommand("bulk_update_photos",i,e.activeSubentryId||null);e.photosSelectedIds.clear(),t.deletePhotos&&(e.photosSelectMode=!1),a&&e.ingestPayload(a,!1);let n=a?.bulk_result?.deleted_ids?.length??0,s=a?.bulk_result?.updated??o.length;e.showToast(t.deletePhotos?e.t("photos.bulk_deleted_toast",{count:n||o.length}):e.t("photos.bulk_updated_toast",{count:s}))}catch(a){e.showToast(G(a,"Could not update selected photos"),!0)}}function br(e){let t=Array.from(e.photosSelectedIds).filter(o=>{let i=(e.state?.system_wallpapers||[]).find(a=>a.id===o);return i?Ge(i):!1});t.length!==0&&e.openConfirm({kind:"bulk_delete_photos",title:e.t("confirm.delete_photos_bulk.title",{count:t.length}),consequence:e.t("confirm.delete_photos_bulk.body"),confirmLabel:e.t("confirm.delete_photos_bulk.confirm"),danger:!0,onConfirm:async()=>{e.photosSelectedIds.clear();for(let o of t)e.photosSelectedIds.add(o);await Ya(e,{deletePhotos:!0})}})}async function Za(e,t,o){e.mediaImportModal={...e.mediaImportModal,loading:!0,error:"",selectedPaths:[]},e.host.requestUpdate();try{let i=await e.ws.browseMediaFolder(t,o),a=(i.subpath||"").split("/").filter(Boolean).pop()||i.root||"";e.mediaImportModal={...e.mediaImportModal,loading:!1,error:"",roots:i.roots||[],root:i.root||"",subpath:i.subpath||"",parentSubpath:i.parent_subpath??null,folders:i.folders||[],images:i.images||[],selectedPaths:[],newCollectionName:e.mediaImportModal.useNewFolderCollection?a:e.mediaImportModal.newCollectionName}}catch(i){e.mediaImportModal={...e.mediaImportModal,loading:!1,error:G(i,"Could not browse Home Assistant Media")}}e.host.requestUpdate()}function fr(e){let t=e.photosFilterCollection.startsWith("col_")?e.photosFilterCollection:"";e.mediaImportModal={...eo(),open:!0,collectionId:t},e.host.requestUpdate(),Za(e)}function yr(e){e.mediaImportModal.importing||(e.mediaImportModal=eo(),e.host.requestUpdate())}async function wr(e){let t=e.mediaImportModal;if(!(t.importing||!t.root||t.selectedPaths.length===0)){e.mediaImportModal={...t,importing:!0},e.host.requestUpdate();try{let o={root:t.root,paths:[...t.selectedPaths],deduplicate:t.deduplicate};t.useNewFolderCollection&&t.newCollectionName.trim()?o.new_collection_name=t.newCollectionName.trim():t.collectionId&&(o.collection_id=t.collectionId);let i=await e.ws.runSystemCommand("import_media_photos",o,e.activeSubentryId||null);e.mediaImportModal=eo(),i?e.ingestPayload(i,!1):e.host.requestUpdate();let a=i?.import_result,n=a?.imported??t.selectedPaths.length,s=a?.skipped??0,r=a?.failed?.length??0;e.showToast(e.t("media_import.summary_toast",{imported:n,skippedSuffix:s>0?e.t("media_import.skipped_suffix",{count:s}):"",failedSuffix:r>0?e.t("media_import.failed_suffix",{count:r}):""}))}catch(o){e.mediaImportModal={...e.mediaImportModal,importing:!1},e.host.requestUpdate(),e.showToast(G(o,"Media import failed"),!0)}}}async function Fo(e,t,o){let i=e.activeSubentryId;if(!i)return!1;let a={target:t.target,mode:t.mode};t.sourceId!==void 0&&(a.source_id=t.sourceId),t.collectionId!==void 0&&(a.collection_id=t.collectionId),t.photoIds!==void 0&&(a.photo_ids=[...t.photoIds]),t.cycleMinutes!==void 0&&(a.cycle_minutes=t.cycleMinutes),t.shuffle!==void 0&&(a.shuffle=t.shuffle);try{let n=await e.ws.runDeviceCommand(i,"set_device_photo_pool",a);return n&&e.activeSubentryId===i&&e.ingestPayload(n,!1),o?e.showToast(o):e.announcePolite(e.t("shell.saved_status")),!0}catch(n){return e.showToast(G(n,"Could not update photo pool"),!0),!1}}function Sr(e,t){let o=e.state?.config||{},i=t==="screensaver",a=(e.state?.wallpapers&&e.state.wallpapers.length>0?e.state.wallpapers:e.state?.system_wallpapers)||[],n=String(i?o.screensaver_photo_mode||"off":o.wallpaper_mode||"off"),s=n==="collection"?"collection":"photos",r=String(i?o.screensaver_photo_source||"":o.wallpaper_source||""),c=String(i?o.screensaver_photo_collection||de:o.wallpaper_collection||de),u=Array.isArray(i?o.screensaver_photo_ids:o.wallpaper_favorites)?i?o.screensaver_photo_ids:o.wallpaper_favorites:[],p=n==="single"?r?[r]:[]:n==="custom"||u.length>0?u:r?[r]:[],d=Ci(p,a,i);e.photoPickerModal={open:!0,target:t,mode:s,collectionId:c||de,selectedIds:d,search:"",filterCollection:de,busy:!1},e.host.requestUpdate()}function kr(e){e.photoPickerModal.busy||(e.photoPickerModal=Mt(),e.host.requestUpdate())}async function $r(e){let t=e.photoPickerModal;if(!t.open||t.busy)return;let o=t.target==="screensaver",i=(e.state?.wallpapers&&e.state.wallpapers.length>0?e.state.wallpapers:e.state?.system_wallpapers)||[],a=Ci(t.selectedIds,i,o);e.photoPickerModal={...t,selectedIds:a,busy:!0},e.host.requestUpdate();let n=e.state?.config||{},s=Number(o?n.screensaver_cycle_minutes??15:n.wallpaper_cycle_minutes??0),r=t.mode==="collection"?"collection":a.length===1?"single":"custom",c=r==="single"?0:s>0?s:15;await Fo(e,{target:t.target,mode:r,sourceId:r==="single"?a[0]:void 0,collectionId:r==="collection"?t.collectionId:void 0,photoIds:r==="custom"?a:void 0,cycleMinutes:c,shuffle:o?!!n.screensaver_shuffle:void 0})?e.photoPickerModal=Mt():e.photoPickerModal={...e.photoPickerModal,busy:!1},e.host.requestUpdate()}var Cr=220,Ai=class{store;editSeqCounter=0;systemSaveChain=Promise.resolve();inFlightSystemPatch={};systemKeySeqs=new Map;pendingSystemKeySeqs={};deviceSaveChains=new Map;inFlightDevicePatches=new Map;deviceKeySeqs=new Map;constructor(t){this.store=t}getEffectiveSystemPatch(){return{...this.inFlightSystemPatch,...this.store.pendingSystemPatch}}getEffectiveDevicePatch(t){let o=this.inFlightDevicePatches.get(t)||{},i=this.store.pendingDeviceBuckets.get(t)?.patch||{};return{...o,...i}}discardDeviceBucket(t){let o=this.store.pendingDeviceBuckets.get(t);o?.timer&&(clearTimeout(o.timer),o.timer=null),this.store.pendingDeviceBuckets.delete(t),this.inFlightDevicePatches.delete(t)}getDeviceKeySeqMap(t){let o=this.deviceKeySeqs.get(t);return o||(o=new Map,this.deviceKeySeqs.set(t,o)),o}stageDeviceSetting(t,o,i,a=Cr){let n=this.store.activeSubentryId;if(!n||this.store.deviceLoading)return;let s=this.store.pendingDeviceBuckets.get(n),r=this.store.state?.system_devices?.find(_=>_.subentry_id===n),c=(this.store.state?.subentry_id===n?this.store.state.title:"")||r?.title||n;s||(s={targetSubentryId:n,targetTitle:c,patch:{},previousValues:{},keySeqs:{},timer:null},this.store.pendingDeviceBuckets.set(n,s));let u=this.store.state&&this.store.state.subentry_id===n?this.store.state.config||{}:{},p=s,d=_=>{_ in p.previousValues||(p.previousValues[_]=u[_])};d(t),d("device_group"),t==="home_screen_enabled"&&d("start_screen"),i&&!(`__dom:${i}`in p.previousValues)&&(p.previousValues[`__dom:${i}`]=p.previousValues[t]);let m=++this.editSeqCounter,g=this.getDeviceKeySeqMap(n);if(g.set(t,m),p.keySeqs[t]=m,i&&(g.set(`__dom:${i}`,m),p.keySeqs[`__dom:${i}`]=m),p.patch[t]=o,this.store.state){let _=t==="device_remote_group"&&Array.isArray(this.store.state.system_devices)?this.store.state.system_devices.map(h=>h.subentry_id===n?{...h,device_remote_group:String(o||"area_auto")}:h):this.store.state.system_devices;if(this.store.state.subentry_id===n){let h={...this.store.state,system_devices:_,config:{...this.store.state.config}};Dt(h,{[t]:o}),this.store.state=h}else _!==this.store.state.system_devices&&(this.store.state={...this.store.state,system_devices:_})}p.timer&&clearTimeout(p.timer),p.timer=setTimeout(()=>{this.flushDeviceBucket(n)},Math.max(0,a)),this.store.host.requestUpdate()}flushDeviceBucket(t){let o=this.store.pendingDeviceBuckets.get(t),i=this.deviceSaveChains.get(t)??Promise.resolve();if(!o)return i;o.timer&&(clearTimeout(o.timer),o.timer=null);let a={...o.patch},n={...o.previousValues},s={...o.keySeqs},r=o.targetTitle;if(this.store.pendingDeviceBuckets.delete(t),Object.keys(a).length===0)return i;let c=this.inFlightDevicePatches.get(t)||{};Object.assign(c,a),this.inFlightDevicePatches.set(t,c);let u=i.then(async()=>{let p=this.getDeviceKeySeqMap(t),d=()=>{let _=this.inFlightDevicePatches.get(t);if(_){for(let h of Object.keys(a))p.get(h)===s[h]&&delete _[h];Object.keys(_).length===0&&this.inFlightDevicePatches.delete(t)}},m=this.store.getKnownDeviceConfigRev(t),g={config:a};m>0&&(g.expected_config_rev=m);try{let _=await this.store.ws.runDeviceCommand(t,"save_device_config",g);d(),_&&(_.subentry_id===t&&_.device_config_rev>0&&this.store.recordKnownDeviceConfigRev(t,_.device_config_rev),this.store.activeSubentryId===t?this.store.ingestPayload(_,!1):this.store.state&&Array.isArray(_.system_devices)&&(this.store.state={...this.store.state,system_devices:_.system_devices,issues:_.issues??this.store.state.issues},this.store.host.requestUpdate())),this.store.announcePolite(this.store.t("shell.saved_status"))}catch(_){if(d(),Xt(_)){await this.store.refreshState(),this.store.showToast(this.store.t("sync.conflict_reloaded"),!0);return}let h={};for(let[k,w]of Object.entries(n))if(k.startsWith("__dom:")){if(p.get(k)!==s[k])continue;let M=k.slice(6);typeof w=="boolean"?h[M]=w:w!=null?h[M]=String(w):h[M]=""}let b="device_remote_group"in n&&p.get("device_remote_group")===s.device_remote_group;if(this.store.state){let k=b&&Array.isArray(this.store.state.system_devices)?this.store.state.system_devices.map(w=>w.subentry_id===t?{...w,device_remote_group:String(n.device_remote_group||"area_auto")}:w):this.store.state.system_devices;if(this.store.state.subentry_id===t){let w={...this.store.state.config},M={};for(let[$,P]of Object.entries(n))$.startsWith("__dom:")||$ in s&&p.get($)!==s[$]||(P===void 0?delete w[$]:(w[$]=P,M[$]=P));let E={...this.store.state,system_devices:k,config:w};Object.keys(M).length>0&&Dt(E,M);let N=this.getEffectiveDevicePatch(t);Object.keys(N).length>0&&Dt(E,N),this.store.state=E}else k!==this.store.state.system_devices&&(this.store.state={...this.store.state,system_devices:k})}this.store.activeSubentryId===t&&Object.keys(h).length>0&&this.store.mergeDomRevert(h);let y=G(_,this.store.t("sync.save_device_failed")),f=this.store.activeSubentryId!==t&&r?this.store.t("sync.save_device_named_failed",{title:r,error:y}):y;this.store.showToast(f,!0),this.store.host.requestUpdate()}});return this.deviceSaveChains.set(t,u),u}stageSystemSetting(t,o,i,a=Cr){let n=String(t);if(!(n in this.store.pendingSystemPrevious)){let r=this.store.state?.system_config?.[n];qa(n)&&Array.isArray(r)?this.store.pendingSystemPrevious[n]=Qe(r,Je[n]):this.store.pendingSystemPrevious[n]=r!==void 0?structuredClone(r):void 0}if(i&&!(`__dom:${i}`in this.store.pendingSystemPrevious)){let r=this.store.pendingSystemPrevious[n];(typeof r=="string"||typeof r=="number"||typeof r=="boolean")&&(this.store.pendingSystemPrevious[`__dom:${i}`]=r)}let s=++this.editSeqCounter;this.systemKeySeqs.set(n,s),this.pendingSystemKeySeqs[n]=s,i&&(this.systemKeySeqs.set(`__dom:${i}`,s),this.pendingSystemKeySeqs[`__dom:${i}`]=s),this.store.pendingSystemPatch[n]=o,this.store.state?.system_config&&(this.store.state={...this.store.state,system_config:{...this.store.state.system_config,[n]:o}}),this.store.systemSaveTimer&&clearTimeout(this.store.systemSaveTimer),this.store.systemSaveTimer=setTimeout(()=>{this.flushSystemSettings()},Math.max(0,a)),this.store.host.requestUpdate()}flushSystemSettings(){this.store.systemSaveTimer&&(clearTimeout(this.store.systemSaveTimer),this.store.systemSaveTimer=null);let t={...this.store.pendingSystemPatch},o={...this.store.pendingSystemPrevious},i={...this.pendingSystemKeySeqs};return this.store.pendingSystemPatch={},this.store.pendingSystemPrevious={},this.pendingSystemKeySeqs={},Object.keys(t).length===0?this.systemSaveChain:(Object.assign(this.inFlightSystemPatch,t),this.systemSaveChain=this.systemSaveChain.then(async()=>{let a=()=>{for(let r of Object.keys(t))this.systemKeySeqs.get(r)===i[r]&&delete this.inFlightSystemPatch[r]},n=this.store.state?.system_config_rev??0,s={config:t};n>0&&(s.expected_config_rev=n);try{let r=await this.store.ws.runSystemCommand("save_system_config",s,this.store.activeSubentryId||null);a(),r&&this.store.ingestPayload(r,!1),this.store.announcePolite(this.store.t("shell.saved_status"))}catch(r){if(a(),Xt(r)){await this.store.refreshState(),this.store.showToast(this.store.t("sync.conflict_reloaded"),!0);return}let c={};if(this.store.state?.system_config){let u=this.store.state.system_config,p={...u};for(let[g,_]of Object.entries(o))if(!(g in i&&this.systemKeySeqs.get(g)!==i[g]))if(g.startsWith("__dom:")){let h=g.slice(6);c[h]=typeof _=="boolean"?_:String(_??"")}else _===void 0?delete p[g]:p[g]=_;let d=this.getEffectiveSystemPatch();Object.assign(p,d);let m={...this.store.state,system_config:p};to(this.store,m,u),this.store.state=m}Object.keys(c).length>0&&this.store.mergeDomRevert(c),this.store.showToast(G(r,this.store.t("sync.save_system_failed")),!0),this.store.host.requestUpdate()}}),this.systemSaveChain)}async flushAllPendingSettings(){let t=[];Object.keys(this.store.pendingSystemPatch).length>0&&t.push(this.flushSystemSettings());for(let o of Array.from(this.store.pendingDeviceBuckets.keys()))t.push(this.flushDeviceBucket(o));await Promise.allSettled(t)}};var io={area_categories:{key:"area_categories",catalog:At,defaultTokens:_a,minRequired:1,noun:"Area category",allowEmpty:!1,checkPrefFallback:!1},home_categories:{key:"home_categories",catalog:Et,defaultTokens:va,minRequired:1,noun:"Home category",allowEmpty:!1,checkPrefFallback:!1},tools_items:{key:"tools_items",catalog:it,defaultTokens:fa,minRequired:1,noun:"tool",allowEmpty:!1,checkPrefFallback:!0},games_items:{key:"games_items",catalog:It,defaultTokens:wa,minRequired:1,noun:"game",allowEmpty:!1,checkPrefFallback:!0},activity_sources:{key:"activity_sources",catalog:ut,defaultTokens:ma,minRequired:0,noun:"source",allowEmpty:!0,checkPrefFallback:!1}};function ao(e,t){let o=new Map(t.catalog.map(c=>[c.token,c])),i=c=>{let u=o.get(c);return u?me(u,e.state?.capabilities):!1},a=()=>{let c=e.state?.config?.[t.key],u=t.checkPrefFallback?e.entity.getPref(t.key)?.value:void 0,p=c??u;if(p==null)return[...t.defaultTokens];let d=String(p);if(!d.trim())return t.allowEmpty?[]:[...t.defaultTokens];let m=d.split(",").map(g=>g.trim().toLowerCase()).filter((g,_,h)=>!!g&&o.has(g)&&h.indexOf(g)===_);return m.length===0&&!t.allowEmpty?[...t.defaultTokens]:m};return{getEnabled:a,toggle:(c,u)=>{let p=String(c||"").trim().toLowerCase();if(!o.has(p))return;let d=a(),m=d.indexOf(p),g=m>=0,_=u!==void 0?!!u:!g;if(_!==g){if(_)d.push(p);else{if(t.minRequired>0){let h=d.filter(b=>i(b));if(d.length<=t.minRequired||i(p)&&h.length<=t.minRequired){e.showToast(e.t("common.keep_one_enabled",{noun:t.noun}),!0);return}}d.splice(m,1)}e.entity.stageDeviceSetting(t.key,d.join(","))}},move:(c,u)=>{let p=String(c||"").trim().toLowerCase(),d=a(),m=d.indexOf(p);if(m<0)return;let g=m+u;for(;g>=0&&g<d.length;){let b=d[g];if(b!==void 0&&i(b))break;g+=u}if(g<0||g>=d.length)return;let _=d[m],h=d[g];_===void 0||h===void 0||(d[m]=h,d[g]=_,e.entity.stageDeviceSetting(t.key,d.join(",")))},reorder:(c,u)=>{let p=a(),d=[];for(let _=0;_<p.length;_+=1){let h=p[_];h!==void 0&&i(h)&&d.push(_)}if(c<0||u<0||c>=d.length||u>=d.length||c===u)return;let m=d.map(_=>p[_]).filter(_=>_!==void 0),[g]=m.splice(c,1);if(g!==void 0){m.splice(u,0,g);for(let _=0;_<d.length;_+=1){let h=d[_],b=m[_];h!==void 0&&b!==void 0&&(p[h]=b)}e.entity.stageDeviceSetting(t.key,p.join(","))}}}}function Xa(e){let t=String(e??""),o="",i=!0;for(let n of t){let s=n.charCodeAt(0);if(s<32||s===127||n==="|"||n===""||n===""||n===" "||n==="	"||n==="\r"||n===`
`){i||(o+=" ",i=!0);continue}o+=n,i=!1}let a=o.trim();return a.length>wo?a.slice(0,wo).trimEnd():a}var kd=new Set(["primary","gold","green","red","orange"]);function Lt(e){return String(e??"").trim().toLowerCase()==="inverted"?"inverted":""}function Ot(e){let t=String(e??"").trim().toLowerCase();return!t||t==="default"?"":kd.has(t)?t:""}function Bt(e,t){let o=["shortcut-icon-badge"];Lt(e)==="inverted"&&o.push("badge-inverted");let i=Ot(t);return i&&o.push(`accent-${i}`),o.join(" ")}function Ja(e){return e.kind==="route"&&Ue.includes(e.target)&&!e.label&&!e.icon&&!Lt(e.badge_style)&&!Ot(e.accent)}function Ei(){return fo.map(e=>({kind:"route",target:e,action:"",label:"",icon:"",confirm:!1,badge_style:"",accent:""}))}function Qa(e,t){if(!Array.isArray(e))return t?Ei():[];let o=new Map(Be.map(s=>[s.token,s])),i=t?at:yo,a=[],n=new Set;for(let s of e){if(!s||typeof s!="object")continue;let r=s,c=String(r.kind||"").trim().toLowerCase();if(c==="route"){let u=String(r.target||"").trim().toLowerCase();if(t&&(u==="settings:root"||u==="app:settings"))continue;let p=o.get(u);if(!p||!t&&p.dockOnly)continue;let d=`route|${u}|`;if(n.has(d))continue;n.add(d);let m=t&&Ue.includes(u);a.push({kind:"route",target:u,action:"",label:m?"":Xa(r.label),icon:m?"":st(r.icon),confirm:!1,badge_style:m?"":Lt(r.badge_style),accent:m?"":Ot(r.accent)})}else if(c==="entity"){let u=String(r.target||"").trim().toLowerCase(),p=u.indexOf(".");if(p<=0)continue;let d=u.slice(0,p),m=Xe[d],g=m?.[0];if(!m||!g)continue;let _=String(r.action||"").trim().toLowerCase(),h=m.some(y=>y.action===_)?_:g.action,b=`entity|${u}|${h}`;if(n.has(b))continue;n.add(b),a.push({kind:"entity",target:u,action:h,label:Xa(r.label),icon:st(r.icon),confirm:r.confirm===void 0?t:!!r.confirm,badge_style:Lt(r.badge_style),accent:Ot(r.accent)})}if(a.length>=i)break}return a}function Tr(e,t,o=null){let i=t==="dock_items";t==="pinned_items"&&e.appConfigModal?.open&&e.appConfigModal.app==="pinned"?(e.returnToPinnedModal=!0,e.appConfigModal={open:!1,app:null}):e.returnToPinnedModal=!1;let a=i?e.entity.getDockItems():e.entity.getPinnedItems(),n=e.state?.capabilities,r=Be.filter(g=>!i&&g.dockOnly||i&&(g.token==="settings:root"||Ue.includes(g.token))?!1:me(g,n))[0]?.token||"weather:moon",c=e.state?.catalog?.shortcut_entities||[],u=c[0],p=u?u.domain:"light",d=Xe[p]?.[0]?.action||"toggle",m=o!==null&&o>=0&&o<a.length?a[o]:void 0;if(m&&o!==null){let g=Lt(m.badge_style),_=Ot(m.accent);if(m.kind==="entity"){let h=m.target.split(".",1)[0]||p;e.shortcutModal={open:!0,listKey:t,editIndex:o,kind:"entity",routeTarget:r,entityDomainFilter:"all",entitySearch:"",entityTarget:m.target,action:m.action||Xe[h]?.[0]?.action||"toggle",label:m.label,icon:m.icon,iconSearch:"",iconStyleFilter:"all",badgeStyle:g,accent:_,confirm:!!m.confirm}}else e.shortcutModal={open:!0,listKey:t,editIndex:o,kind:"route",routeTarget:m.target,entityDomainFilter:"all",entitySearch:"",entityTarget:u?.id||"",action:d,label:m.label,icon:m.icon,iconSearch:"",iconStyleFilter:"all",badgeStyle:g,accent:_,confirm:i}}else e.shortcutModal={open:!0,listKey:t,editIndex:null,kind:i?"route":c.length>0?"entity":"route",routeTarget:r,entityDomainFilter:"all",entitySearch:"",entityTarget:u?.id||"",action:d,label:"",icon:"",iconSearch:"",iconStyleFilter:"all",badgeStyle:"",accent:"",confirm:i};e.host.requestUpdate(),Ds().then(()=>{e.shortcutModal.open&&e.host.requestUpdate()}).catch(()=>{})}function xr(e){let t=e.shortcutModal,o=t.listKey==="dock_items",i=o?at:yo,a=(o?e.entity.getDockItems():e.entity.getPinnedItems()).map(_=>({..._}));if(t.editIndex===null&&a.length>=i){e.showToast(`${o?"App Dock":"Pinned app"} supports up to ${i} shortcuts`,!0);return}let n=t.icon.trim(),s=t.iconSearch.trim(),r="";if(n){let _=st(n);if(!_||!Ro(_)){e.showToast("Select a supported Material Design Icon",!0);return}r=_}else if(s){let _=st(s);if(_&&Ro(_))r=_;else{e.showToast("Click one of the matching icons below (or clear the icon search)",!0);return}}let c=Xa(t.label),u=Lt(t.badgeStyle),p=Ot(t.accent),d;if(t.kind==="route"){let _=t.routeTarget.trim().toLowerCase(),h=Be.find(b=>b.token===_);if(!h||!o&&h.dockOnly||o&&(_==="settings:root"||Ue.includes(_))||!me(h,e.state?.capabilities)){e.showToast("Select an app or page to pin",!0);return}d={kind:"route",target:_,action:"",label:c,icon:r,confirm:!1,badge_style:u,accent:p}}else{let _=t.entityTarget.trim().toLowerCase(),h=_.indexOf(".");if(h<=0){e.showToast("Select a Home Assistant entity",!0);return}let b=_.slice(0,h),y=Xe[b]||[],f=y.some(k=>k.action===t.action)?t.action:y[0]?.action||"";if(!f){e.showToast(`Unsupported entity domain '${b}'`,!0);return}d={kind:"entity",target:_,action:f,label:c,icon:r,confirm:!!t.confirm,badge_style:u,accent:p}}if(a.findIndex((_,h)=>h!==t.editIndex&&_.kind===d.kind&&_.target===d.target&&_.action===d.action)>=0){e.showToast("That shortcut is already in this list",!0);return}t.editIndex!==null&&t.editIndex>=0&&t.editIndex<a.length?a[t.editIndex]=d:a.push(d);let g=!!e.returnToPinnedModal;e.returnToPinnedModal=!1,e.shortcutModal={...e.shortcutModal,open:!1},g&&(e.appConfigModal={open:!0,app:"pinned"}),e.entity.stageDeviceSetting(t.listKey,a)}var $d=8e3,Cd=new Set(ca),Ii=class{store;saves;cameraPreviewCache=new Map;tokenLists;constructor(t){this.store=t,this.saves=new Ai(t),this.tokenLists={area_categories:ao(t,io.area_categories),home_categories:ao(t,io.home_categories),tools_items:ao(t,io.tools_items),games_items:ao(t,io.games_items),activity_sources:ao(t,io.activity_sources)}}isCatalogItemSupported(t,o){return me(t,o??this.store.state?.capabilities)}getEffectiveSystemPatch(){return this.saves.getEffectiveSystemPatch()}getEffectiveDevicePatch(t){return this.saves.getEffectiveDevicePatch(t)}discardDeviceBucket(t){this.saves.discardDeviceBucket(t)}stageDeviceSetting(t,o,i,a){this.saves.stageDeviceSetting(t,o,i,a)}flushDeviceBucket(t){return this.saves.flushDeviceBucket(t)}stageSystemSetting(t,o,i,a){this.saves.stageSystemSetting(t,o,i,a)}flushSystemSettings(){return this.saves.flushSystemSettings()}flushAllPendingSettings(){return this.saves.flushAllPendingSettings()}getPref(t){return(this.store.state?.device_prefs||[]).find(o=>o.key===t)}getPrefs(t){let o=this.store.state?.device_prefs||[];if(!t||t.length===0)return o;let i=new Set(t);return o.filter(a=>i.has(a.key))}getPrefSpec(t){return this.store.state?.pref_specs?.find(i=>i.key===t)??pt[t]}getSectionItems(t){return(this.store.state?.esphome?.sections||[]).find(i=>i.id===t)?.items||[]}currentEntityState(t){for(let o of this.store.state?.esphome?.sections||[])for(let i of o.items||[])if(i.entity_id===t)return i.state;return""}applyOptimisticEntity(t,o){let i=this.currentEntityState(t);if(this.store.pendingEntityStates.set(t,{state:o,previousValue:i,expires:Date.now()+$d}),this.store.state?.esphome?.sections){let a={...this.store.state};No(a,this.store.pendingEntityStates),this.store.state=a,this.store.host.requestUpdate()}return i}rollbackOptimisticEntity(t,o){this.store.pendingEntityStates.delete(t),this.store.state?.esphome?.sections&&(this.store.state={...this.store.state,esphome:{...this.store.state.esphome,sections:this.store.state.esphome.sections.map(i=>({...i,items:(i.items||[]).map(a=>a.entity_id===t?{...a,state:o}:a)}))}}),this.store.host.requestUpdate()}async executeEntityAction(t,o,i,a){let n=this.store.activeSubentryId;if(!n||!t)return!1;let s=o!==void 0?this.applyOptimisticEntity(t,o):"";try{let r=await this.store.ws.runDeviceCommand(n,"esphome_entity_action",{entity_id:t,...i});return r&&this.store.activeSubentryId===n&&this.store.ingestPayload(r,!1),!0}catch(r){return o!==void 0&&this.rollbackOptimisticEntity(t,s),this.store.showToast(G(r,a),!0),!1}}async espAction(t,o,i,a){let n=await this.executeEntityAction(t,i,{action:o},"Device action failed");return n&&a&&this.store.showToast(a),n}async espSelect(t,o){await this.executeEntityAction(t,o,{option:o},"Could not update option")}async espNumber(t,o){Number.isFinite(o)&&await this.executeEntityAction(t,String(o),{level:o},"Could not update level")}async runDeviceAction(t,o){let i=this.store.activeSubentryId,a=String(t||"").trim().toLowerCase();if(!i||!a)return!1;if(!Cd.has(a))return this.store.showToast(`Unsupported Device action: ${a}`,!0),!1;try{let n=await this.store.ws.runDeviceCommand(i,"device_action",{action:a});return n&&this.store.activeSubentryId===i&&this.store.ingestPayload(n,!1),o&&this.store.showToast(o),!0}catch(n){return this.store.showToast(G(n,"Device action failed"),!0),!1}}async triggerHeaderFirmwareUpdate(){let t=this.store.state?.live?.fw_update_entity||"";t&&await this.espAction(t,"install")&&this.store.showToast("Firmware update started")}getEnabledAreaCategories(){return this.tokenLists.area_categories.getEnabled()}toggleAreaCategoryToken(t,o){this.tokenLists.area_categories.toggle(t,o)}moveAreaCategoryToken(t,o){this.tokenLists.area_categories.move(t,o)}reorderAreaCategories(t,o){this.tokenLists.area_categories.reorder(t,o)}getEnabledHomeCategories(){return this.tokenLists.home_categories.getEnabled()}toggleHomeCategoryToken(t,o){this.tokenLists.home_categories.toggle(t,o)}moveHomeCategoryToken(t,o){this.tokenLists.home_categories.move(t,o)}reorderHomeCategories(t,o){this.tokenLists.home_categories.reorder(t,o)}getEnabledToolsItems(){return this.tokenLists.tools_items.getEnabled()}toggleToolItemToken(t,o){this.tokenLists.tools_items.toggle(t,o)}moveToolItemToken(t,o){this.tokenLists.tools_items.move(t,o)}reorderToolsItems(t,o){this.tokenLists.tools_items.reorder(t,o)}getEnabledGamesItems(){return this.tokenLists.games_items.getEnabled()}toggleGameItemToken(t,o){this.tokenLists.games_items.toggle(t,o)}moveGameItemToken(t,o){this.tokenLists.games_items.move(t,o)}reorderGamesItems(t,o){this.tokenLists.games_items.reorder(t,o)}getEnabledActivitySources(){return this.tokenLists.activity_sources.getEnabled()}toggleActivitySource(t,o){this.tokenLists.activity_sources.toggle(t,o)}reorderActivitySources(t,o){this.tokenLists.activity_sources.reorder(t,o)}getSystemBroadcastSpeakers(){return Ho(this.store)}getBroadcastSpeakers(){return ki(this.store)}toggleBroadcastSpeaker(t,o){er(this.store,t,o)}reorderBroadcastSpeakers(t,o){tr(this.store,t,o)}getSystemCameraEntities(){return Uo(this.store)}getVisibleCameras(){return Rt(this.store)}toggleVisibleCamera(t,o){or(this.store,t,o)}reorderVisibleCameras(t,o){ir(this.store,t,o)}getCarouselCameras(){return $i(this.store)}toggleCarouselCamera(t,o){ar(this.store,t,o)}reorderCarouselCameras(t,o){nr(this.store,t,o)}getDockItems(){let t=this.store.state?.config?.dock_items;return t==null?Ei():Qa(t,!0)}getPinnedItems(){let t=this.store.state?.config?.pinned_items;return t==null?[]:Qa(t,!1)}moveShortcutItem(t,o,i){this.reorderShortcutItems(t,o,o+i)}reorderShortcutItems(t,o,i){let a=t==="dock_items"?this.getDockItems():this.getPinnedItems();if(o<0||i<0||o>=a.length||i>=a.length||o===i)return;let n=a.map(r=>({...r})),[s]=n.splice(o,1);s&&(n.splice(i,0,s),this.stageDeviceSetting(t,n))}removeShortcutItem(t,o){let i=t==="dock_items"?this.getDockItems():this.getPinnedItems();if(o<0||o>=i.length)return;let a=i.filter((n,s)=>s!==o).map(n=>({...n}));this.stageDeviceSetting(t,a)}resetDockItemsToDefault(){this.stageDeviceSetting("dock_items",Ei()),this.store.showToast("Restored default App Dock")}requestResetDockItems(){this.store.openConfirm({kind:"reset_dock",title:this.store.t("confirm.reset_dock.title"),consequence:this.store.t("confirm.reset_dock.body"),confirmLabel:this.store.t("confirm.reset_dock.confirm"),danger:!0,blastRadiusCount:1,onConfirm:()=>{this.resetDockItemsToDefault()}})}toggleNativeDockApp(t,o){let i=String(t||"").trim().toLowerCase();if(!Ue.includes(i))return;let a=this.getDockItems().map(n=>({...n}));if(!o){let n=a.filter(s=>!(s.kind==="route"&&s.target===i));this.stageDeviceSetting("dock_items",n);return}if(!a.some(n=>n.kind==="route"&&n.target===i)){if(a.length>=at){this.store.showToast(`App Dock supports up to ${at} shortcuts`,!0);return}a.push({kind:"route",target:i,action:"",label:"",icon:"",confirm:!1,badge_style:"",accent:""}),this.stageDeviceSetting("dock_items",a)}}openAppConfigModal(t){this.store.returnToPinnedModal=!1,this.store.shortcutModal.open&&(this.store.shortcutModal={...this.store.shortcutModal,open:!1}),this.store.appConfigModal={open:!0,app:t},this.store.host.requestUpdate()}closeAppConfigModal(){this.store.appConfigModal={open:!1,app:null},this.store.host.requestUpdate()}openShortcutModal(t,o=null){Tr(this.store,t,o)}closeShortcutModal(){let t=this.store.returnToPinnedModal;this.store.returnToPinnedModal=!1,this.store.shortcutModal={...this.store.shortcutModal,open:!1},t&&(this.store.appConfigModal={open:!0,app:"pinned"}),this.store.host.requestUpdate()}saveShortcutModal(){xr(this.store)}applyDeviceCustomColor(t,o=!0){ue(t)&&(this.stageDeviceSetting("device_custom_color",t.toUpperCase()),o&&this.stageDeviceSetting("color_profile","Custom"))}deleteCustomPalette(t){let o=t.toUpperCase(),i=(this.store.state?.system_config?.custom_palettes||[]).filter(a=>a.hex.toUpperCase()!==o);this.stageSystemSetting("custom_palettes",i)}openPhotoUploadModal(t){rr(this.store,t)}closePhotoUploadModal(){lr(this.store)}stageUploadFiles(t){cr(this.store,t)}removeStagedUpload(t){dr(this.store,t)}async uploadAllStagedPhotos(){await ur(this.store)}openPhotoEditModal(t){pr(this.store,t)}closePhotoEditModal(){mr(this.store)}async savePhotoEditModal(){await gr(this.store)}async createPhotoCollection(t){return Ka(this.store,t)}async createUploadCollection(){return Wa(this.store)}async renamePhotoCollection(t,o){await _r(this.store,t,o)}requestDeletePhotoCollection(t,o){hr(this.store,t,o)}async deletePhoto(t){await ja(this.store,t)}requestDeletePhoto(t,o){vr(this.store,t,o)}async bulkUpdatePhotos(t){await Ya(this.store,t)}requestBulkDeletePhotos(){br(this.store)}openMediaImportModal(){fr(this.store)}closeMediaImportModal(){yr(this.store)}async browseMediaFolder(t,o){await Za(this.store,t,o)}async importSelectedMedia(){await wr(this.store)}openPhotoPickerModal(t){Sr(this.store,t)}closePhotoPickerModal(){kr(this.store)}async applyPhotoPickerModal(){await $r(this.store)}async setDevicePhotoPool(t,o){return Fo(this.store,t,o)}async setWallpaperRotation(t){let o=this.store.state?.config||{},i=Math.max(0,Math.round(Number(t)||0)),a=String(o.wallpaper_mode||"off");await Fo(this.store,{target:"wallpaper",mode:a,sourceId:String(o.wallpaper_source||""),collectionId:String(o.wallpaper_collection||""),photoIds:Array.isArray(o.wallpaper_favorites)?o.wallpaper_favorites:[],cycleMinutes:i})}async setScreensaverRotation(t,o){let i=this.store.state?.config||{},a=Math.max(0,Math.round(Number(t)||0)),n=String(i.screensaver_photo_mode||"off");await Fo(this.store,{target:"screensaver",mode:n,sourceId:String(i.screensaver_photo_source||""),collectionId:String(i.screensaver_photo_collection||""),photoIds:Array.isArray(i.screensaver_photo_ids)?i.screensaver_photo_ids:[],cycleMinutes:a,shuffle:o!==void 0?o:!!i.screensaver_shuffle})}updateStringListRow(t,o,i){Gs(this.store,t,o,i)}addStringListRow(t,o="",i){zs(this.store,t,o,i)}removeStringListRow(t,o){Ks(this.store,t,o)}moveStringListRow(t,o,i){Ga(this.store,t,o,o+i)}reorderStringListRows(t,o,i){Ga(this.store,t,o,i)}addVolumeOverrideRow(){Ws(this.store)}updateVolumeOverrideRow(t,o,i){js(this.store,t,o,i)}removeVolumeOverrideRow(t){Ys(this.store,t)}addRemoteGroupRow(){Zs(this.store)}updateRemoteGroupField(t,o,i){Xs(this.store,t,o,i)}toggleRemoteInGroup(t,o){Js(this.store,t,o)}removeRemoteGroupRow(t){Qs(this.store,t)}clearCameraPreviewCache(){this.cameraPreviewCache.clear()}async previewCamera(t,o=!1){let i=String(t||"").trim();if(!i){this.closeCameraPreview();return}let a=Date.now(),n=this.cameraPreviewCache.get(i);if(!o&&n&&n.expiresAtMs>a){this.store.activeCameraPreviewEntity=i,this.store.cameraPreviewUrl=n.url,this.store.host.requestUpdate();return}try{let s=await this.store.ws.mintCameraPreviewUrl(i),r=Math.max(30,Number(s.expires_in||600)-30);this.cameraPreviewCache.set(i,{url:s.preview_url,expiresAtMs:a+r*1e3});let c=s.preview_url.includes("?")?"&":"?";this.store.activeCameraPreviewEntity=i,this.store.cameraPreviewUrl=o?`${s.preview_url}${c}_ts=${a}`:s.preview_url,this.store.host.requestUpdate()}catch(s){this.store.showToast(G(s,"Could not load camera preview"),!0)}}closeCameraPreview(){this.store.activeCameraPreviewEntity="",this.store.cameraPreviewUrl="",this.store.host.requestUpdate()}async testDoorbellSpeaker(){let o=(this.store.state?.system_config?.camera_entities||[]).map(a=>String(a||"").trim()).filter(Boolean)[0];if(!o){this.store.showToast("Add a camera in Shared entities first",!0);return}if(!this.store.doorbellTestSubentryId){this.store.showToast("Choose a Device to test from",!0);return}let i=this.store.doorbellTestReply.trim()||"Testing Latter doorbell audio.";await this.flushSystemSettings();try{let a=await this.store.ws.runSystemCommand("test_doorbell_speaker",{subentry_id:this.store.doorbellTestSubentryId,camera_entity:o,message:i},this.store.activeSubentryId||null);a&&this.store.ingestPayload(a,!1),this.store.showToast("Played test message on door speaker")}catch(a){this.store.showToast(G(a,"Door speaker test failed"),!0)}}};function no(e){return String(e||"").split(",").map(t=>t.trim()).filter(Boolean)}var Pi=class{store;batchPillDrafts=new Map;batchBusy=!1;constructor(t){this.store=t}get batchDraft(){return this.store.batchDraft}get batchDraftCount(){let t=new Set(this.store.batchDraft.keys());for(let[o,i]of this.batchPillDrafts.entries())Object.keys(i).length>0&&t.add(o);return t.size}get hasBatchDraft(){return this.batchDraftCount>0}resolvedBatchTargetId(){let t=this.store.batchTargetFilter||"all";return t.startsWith("group:")?t.slice(6):t}setBatchTargetFilter(t){let o=String(t||"all").trim()||"all";this.store.batchTargetFilter!==o&&(this.store.batchTargetFilter=o,this.resetBatchDraft())}matchingBatchDevices(){let t=this.store.batchTargetFilter||"all";return(this.store.state?.system_devices||[]).filter(i=>i.kind!=="ble_tag").filter(i=>{if(t==="all")return!0;if(t==="online")return!!i.is_online;if(t==="roaming")return!!i.is_roaming;if(t==="stationary")return!i.is_roaming;let a=t.startsWith("group:")?t.slice(6):t;return(i.device_group||"custom")===a})}filteredControlTargets(t){let o=this.store.batchTargetFilter||"all";return(t.targets||[]).filter(i=>{if(o==="all")return!0;if(o==="online")return!!i.is_online;if(o==="roaming")return!!i.is_roaming;if(o==="stationary")return!i.is_roaming;let a=o.startsWith("group:")?o.slice(6):o;return(i.device_group||"custom")===a})}getEffectiveBatchValue(t){let o=t.pref_key||"";if(o&&this.store.batchDraft.has(o)){let s=this.store.batchDraft.get(o);return{value:t.domain==="switch"?s?"on":"off":String(s??""),mixed:!1,staged:!0}}let i=this.filteredControlTargets(t),a=i[0];return a?new Set(i.map(s=>String(s.state??""))).size>1?{value:String(a.state??""),mixed:!0,staged:!1}:{value:String(a.state??""),mixed:!1,staged:!1}:{value:String(t.state??""),mixed:!1,staged:!1}}applyTokenDeltasToCsv(t,o,i){let a=no(t),n=new Set(a);for(let[p,d]of Object.entries(o))d?n.add(p):n.delete(p);let s=a.filter(p=>n.has(p)),r=new Set(s),c=i.filter(p=>n.has(p)&&!r.has(p)),u=Array.from(n).filter(p=>!r.has(p)&&!c.includes(p));return[...s,...c,...u].join(",")}getEffectiveBatchPillStates(t){let o=t.pref_key||"",i=t.options||[],a=t.option_labels||{},n=this.filteredControlTargets(t),s=o&&this.batchPillDrafts.get(o)||{},r=o&&this.store.batchDraft.has(o)?String(this.store.batchDraft.get(o)??""):null;return i.map(c=>{let u=a[c]||c;if(r!==null){let m=new Set(no(r));return{token:c,label:u,state:m.has(c)?"on":"off",staged:!0}}if(c in s)return{token:c,label:u,state:s[c]?"on":"off",staged:!0};if(n.length===0)return{token:c,label:u,state:"off",staged:!1};let p=0;for(let m of n)no(m.state).includes(c)&&(p+=1);let d=p===0?"off":p===n.length?"on":"mixed";return{token:c,label:u,state:d,staged:!1}})}stageBatchSetting(t,o){let i=String(t||"").trim();i&&(this.batchPillDrafts.delete(i),this.store.batchDraft.set(i,o),this.store.host.requestUpdate())}stageBatchColor(t,o){let i=String(o||"").trim().toUpperCase();!t.pref_key||!ue(i)||(this.store.batchDraft.set(t.pref_key,i),this.store.batchDraft.set("color_profile","Custom"),this.store.host.requestUpdate())}stageBatchPillToggle(t,o,i){let a=t.pref_key||"",n=String(o||"").trim();if(!a||!n)return;let r=this.getEffectiveBatchPillStates(t).find(_=>_.token===n),c=i!==void 0?!!i:r?.state!=="on",u=this.filteredControlTargets(t),p=t.options||[],d={...this.batchPillDrafts.get(a)||{}};if(this.store.batchDraft.has(a)){let _=new Set(no(String(this.store.batchDraft.get(a)??"")));for(let h of p)d[h]=_.has(h);this.store.batchDraft.delete(a)}let m={...d,[n]:c},g=t.min??0;if(!c&&g>0&&u.length>0&&u.some(h=>{let b=this.applyTokenDeltasToCsv(h.state,m,p);return no(b).length<g})){let h=a==="tools_items"?"tool":a==="games_items"?"game":"category";this.store.showToast(this.store.t("common.keep_one_enabled",{noun:h}),!0);return}u.length>0&&u.every(_=>no(_.state).includes(n)===c)&&delete m[n],Object.keys(m).length===0?this.batchPillDrafts.delete(a):this.batchPillDrafts.set(a,m),this.store.host.requestUpdate()}resetBatchDraft(){this.store.batchDraft.clear(),this.batchPillDrafts.clear(),this.store.host.requestUpdate()}previewBatchDetachmentCount(){return!this.hasBatchDraft||!(this.batchPillDrafts.size>0||Array.from(this.store.batchDraft.keys()).some(o=>{let i=this.store.entity.getPrefSpec(o);return!i||i.group_tier!==null}))?0:this.matchingBatchDevices().filter(o=>!!(o.device_group&&o.device_group!=="custom")).length}requestApplyBatchDraft(){if(!this.hasBatchDraft||this.batchBusy)return;let t=this.matchingBatchDevices();if(t.length===0){this.store.showToast(this.store.t("batch.no_targets"),!0);return}if(t.length===1){this.applyBatchDraft();return}let o=t.length,i=this.batchDraftCount;this.store.openConfirm({kind:"apply_batch",title:this.store.t("confirm.apply_batch.title",{count:o}),consequence:this.store.t("confirm.apply_batch.body",{settingCount:i,count:o}),confirmLabel:this.store.t("confirm.apply_batch.confirm"),danger:!1,blastRadiusCount:o,onConfirm:async()=>{await this.applyBatchDraft()}})}async applyBatchDraft(){if(!this.hasBatchDraft||this.batchBusy)return;let t=this.matchingBatchDevices();if(t.length===0){this.store.showToast(this.store.t("batch.no_targets"),!0);return}let o=new Map,i=new Map;for(let u of t)i.set(u.device_slug,u.subentry_id),u.device_group&&u.device_group!=="custom"&&o.set(u.subentry_id,{title:u.title,group:u.device_group});let a=Object.fromEntries(this.store.batchDraft.entries()),n=new Set,s=new Map,r=this.store.state?.system_controls||[];for(let[u,p]of this.batchPillDrafts.entries()){if(Object.keys(p).length===0)continue;let d=r.find(y=>y.pref_key===u),m=d?.options||[],g=d?this.filteredControlTargets(d):[];if(g.length===0)continue;let _=[];for(let y of g){let f=y.subentry_id||(y.device_slug?i.get(y.device_slug):"")||"",k=this.applyTokenDeltasToCsv(y.state,p,m);f&&_.push({subentryId:f,csv:k})}let h=_[0];if(!h)continue;if(new Set(_.map(y=>y.csv)).size===1)a[u]=h.csv,n.add(u);else for(let y of _){let f=s.get(y.subentryId)||{};f[u]=y.csv,s.set(y.subentryId,f)}}this.batchBusy=!0,this.store.host.requestUpdate();let c=!1;try{let u=null;if(Object.keys(a).length>0){u=await this.store.ws.runSystemCommand("apply_batch_device_setting",{target:this.store.batchTargetFilter||"all",config:a},this.store.activeSubentryId||null),c=!0;for(let _ of Object.keys(a))this.store.batchDraft.delete(_);for(let _ of n)this.batchPillDrafts.delete(_)}let p=new Set(s.keys());for(let[_,h]of s.entries()){let b=this.store.getKnownDeviceConfigRev(_),y={config:h};b>0&&(y.expected_config_rev=b);let f=await this.store.ws.runDeviceCommand(_,"save_device_config",y);c=!0,p.delete(_),f&&(f.subentry_id===_&&f.device_config_rev>0&&this.store.recordKnownDeviceConfigRev(_,f.device_config_rev),u=f)}this.store.batchDraft.clear(),p.size===0&&this.batchPillDrafts.clear(),u&&this.store.ingestPayload(u,!1);let d=this.store.state?.system_devices||[],m=[];for(let[_,h]of o.entries()){let b=d.find(y=>y.subentry_id===_);b&&b.device_group==="custom"&&h.group!=="custom"&&m.push(h.title)}let g=m[0];if(m.length===1&&g!==void 0)this.store.showToast(this.store.t("groups.detached_toast",{title:g}));else if(m.length>1)this.store.showToast(this.store.t("groups.detached_many_toast",{count:m.length}));else{let _=t.length;this.store.showToast(_===1?this.store.t("batch.applied_to_one"):this.store.t("batch.applied_to_n",{count:_}))}}catch(u){(c||Xt(u))&&await this.store.refreshState(),Xt(u)?this.store.showToast(this.store.t("sync.conflict_reloaded"),!0):this.store.showToast(G(u,"Could not apply staged batch settings"),!0)}finally{this.batchBusy=!1,this.store.host.requestUpdate()}}async applyBatchCopyFromDevice(t,o){if(!t||!o.length){this.store.showToast("Choose a template Device first",!0);return}try{let i=await this.store.ws.runSystemCommand("apply_batch_device_setting",{target:this.store.batchTargetFilter||"all",source_subentry_id:t,copy_keys:o},this.store.activeSubentryId||null);i&&this.store.ingestPayload(i,!1),this.store.showToast("Pushed list from template Device")}catch(i){this.store.showToast(G(i,"Could not copy list across target Devices"),!0)}}};function en(e,t){return e.calibratingAllIlluminance?!0:!!(t&&e.calibratingIlluminanceAreas.has(String(t)))}function Ar(e,t){e.bleSurveySubentryId=t,e.host.requestUpdate(),e.ensureSubscription(!1)}function Er(e,t,o=!1){e.bleCalibrateAreaId=String(t||""),o&&(e.handoffTargetIds.clear(),e.bleCalibrateHandoffActive=!0),e.host.requestUpdate(),o&&typeof globalThis.requestAnimationFrame=="function"&&globalThis.requestAnimationFrame(()=>{let i=e.host.renderRoot||e.host.shadowRoot,a=i?.getElementById("card-ble-calibration")||i?.getElementById("ble-calibrate-target-box");a&&typeof a.scrollIntoView=="function"&&a.scrollIntoView({behavior:"smooth",block:"start"});let n=i?.getElementById("ble-calibrate-area-select");if(n&&typeof n.focus=="function")try{n.focus({preventScroll:!0})}catch{n.focus()}})}function Ir(e,t){if(!t){e.bleSurveyFrozen.clear();for(let o of e.state?.system_devices||[])o.subentry_id&&e.bleSurveyFrozen.set(o.subentry_id,{rows:(o.ble_survey_rows||[]).map(i=>({...i})),packetsSeen:o.ble_packets_seen??0,activeAreaName:o.active_area_name||""});e.bleLiveStreamActive=!1,e.host.requestUpdate(),e.ensureSubscription(!1);return}e.bleSurveyFrozen.clear(),e.bleLiveStreamActive=!0,e.host.requestUpdate(),e.ensureSubscription(!1)}function tn(e){return(e.state?.system_devices||[]).filter(i=>i.ble_tracked||i.kind==="ble_tag").find(i=>i.subentry_id===e.bleSurveySubentryId)}async function Pr(e,t,o){let i=String(t||"").trim();if(!i){e.showToast("Missing BLE scanner source",!0);return}try{let a=await e.ws.runSystemCommand("set_ble_scanner_offset",{scanner_source:i,offset_db:o},e.activeSubentryId||null);if(a){if(!e.bleLiveStreamActive&&Array.isArray(a.system_devices)){let n=i.toLowerCase();for(let s of a.system_devices){if(!s.subentry_id)continue;let r=e.bleSurveyFrozen.get(s.subentry_id);if(!r)continue;let c=(s.ble_survey_rows||[]).find(u=>String(u.scanner_source||"").trim().toLowerCase()===n);c&&(r.rows=r.rows.map(u=>String(u.scanner_source||"").trim().toLowerCase()!==n?u:{...u,offset_db:c.offset_db,effective_rssi:c.effective_rssi}))}}e.ingestPayload(a,!1)}}catch(a){e.showToast(G(a,"Could not update BLE scanner offset"),!0)}}async function Mr(e,t){let o=e.state?.system_devices,i=Array.isArray(o)?tn(e)||o.find(n=>n.ble_tracked||n.kind==="ble_tag"):void 0,a=Array.isArray(o)?i?.subentry_id||"":e.bleSurveySubentryId;if(!a){e.showToast("Select a calibration Device first",!0);return}try{let n=await e.ws.runSystemCommand("capture_ble_area_signature",{area_id:t,survey_subentry_id:a},e.activeSubentryId||null);e.bleCalibrateHandoffActive=!1,n?e.ingestPayload(n,!1):e.host?.requestUpdate?.(),e.showToast("Captured Area signature")}catch(n){e.showToast(G(n,"Signature capture failed"),!0)}}async function on(e,t){let o=String(t||"").trim();if(o)try{let i=await e.ws.runSystemCommand("clear_ble_area_signature",{area_id:o},e.activeSubentryId||null);i&&e.ingestPayload(i,!1),e.showToast("Cleared Area signature")}catch(i){e.showToast(G(i,"Could not clear Area signature"),!0)}}function Dr(e,t,o){let i=String(t||"").trim();if(!i)return;let a=o||i;e.openConfirm({kind:"clear_ble_signature",title:e.t("confirm.clear_ble_signature.title",{area:a}),consequence:e.t("confirm.clear_ble_signature.body",{area:a}),confirmLabel:e.t("confirm.clear_ble_signature.confirm"),danger:!0,onConfirm:async()=>{await on(e,i)}})}async function Rr(e,t,o){try{let i=await e.ws.runSystemCommand("set_area_fusion",{area_id:t,...o},e.activeSubentryId||null);i&&e.ingestPayload(i,!1),e.announcePolite(e.t("shell.saved_status"))}catch(i){e.showToast(G(i,"Could not update Area fusion"),!0)}}async function Lr(e,t,o){try{let i=await e.ws.runSystemCommand("set_area_illuminance",{area_id:t,...o},e.activeSubentryId||null);i&&e.ingestPayload(i,!1),e.announcePolite(e.t("shell.saved_status"))}catch(i){e.showToast(G(i,"Could not update Area ambient light"),!0)}}async function Or(e,t,o){if(!en(t,o)){o?t.calibratingIlluminanceAreas.add(o):t.calibratingAllIlluminance=!0,e.host.requestUpdate();try{let i={};o&&(i.area_id=o);let a=await e.ws.runSystemCommand("calibrate_area_illuminance",i,e.activeSubentryId||null);a&&e.ingestPayload(a,!1);let n=a?.calibrated,s=Array.isArray(n)?n:[],r=s[0];s.length===1&&r?e.showToast(e.t("presence_sys.calibrate_lux_one_done",{area:String(r.area_name||""),dark:String(r.dark_lux??0),bright:String(r.bright_lux??40)}),!1):s.length>1&&e.showToast(e.t("presence_sys.calibrate_lux_done",{count:s.length}),!1)}catch(i){e.showToast(G(i,"Could not calibrate Area ambient light"),!0)}finally{o?t.calibratingIlluminanceAreas.delete(o):t.calibratingAllIlluminance=!1,e.host.requestUpdate()}}}function Td(e){return e.trim().toLowerCase().replace(/[^a-z0-9]+/g,"_").replace(/^_+|_+$/g,"")}var Mi=class{store;batch;calibratingAllIlluminance=!1;calibratingIlluminanceAreas=new Set;constructor(t){this.store=t,this.batch=new Pi(t)}get batchPillDrafts(){return this.batch.batchPillDrafts}get batchBusy(){return this.batch.batchBusy}set batchBusy(t){this.batch.batchBusy=t}get batchDraft(){return this.batch.batchDraft}get batchDraftCount(){return this.batch.batchDraftCount}get hasBatchDraft(){return this.batch.hasBatchDraft}isCalibratingIlluminance(t){return en(this,t)}toggleNewGroupForm(t){let o=t!==void 0?!!t:!this.store.newGroupFormOpen;this.store.newGroupFormOpen=o,o||(this.store.newGroupName="",this.store.newGroupDesc="",this.store.newGroupSourceSubentryId="",this.store.newGroupIncludeDisplay=!1,this.store.newGroupIncludeInterface=!1),this.store.host.requestUpdate(),o&&typeof globalThis.requestAnimationFrame=="function"&&globalThis.requestAnimationFrame(()=>{let a=(this.store.host.renderRoot||this.store.host.shadowRoot)?.getElementById("new-group-name");if(a&&typeof a.focus=="function")try{a.focus({preventScroll:!0})}catch{a.focus()}})}async createDeviceGroup(){let t=this.store.newGroupName.trim(),o=this.store.newGroupDesc.trim(),i=this.store.newGroupSourceSubentryId.trim();if(!t){this.store.showToast("Enter a Device group name",!0);return}try{let a={name:t,description:o};i&&(a.source_subentry_id=i),this.store.newGroupIncludeDisplay&&(a.include_display=!0),this.store.newGroupIncludeInterface&&(a.include_interface=!0);let n=await this.store.ws.runSystemCommand("create_device_group",a,this.store.activeSubentryId||null),s=Td(t)||"group";this.store.newGroupFormOpen=!1,this.store.newGroupName="",this.store.newGroupDesc="",this.store.newGroupSourceSubentryId="",this.store.newGroupIncludeDisplay=!1,this.store.newGroupIncludeInterface=!1,this.store.openGroupIds.add(s),n&&this.store.ingestPayload(n,!1),this.store.showToast(`Created group "${t}"`)}catch(a){this.store.showToast(G(a,"Could not create Device group"),!0)}}openSaveGroupModal(){if(!this.store.activeSubentryId)return;let t=this.store.state?.title||"";this.store.saveGroupModal={open:!0,subentryId:this.store.activeSubentryId,name:"",description:t?`Saved from ${t}`:"",includeDisplay:!1,includeInterface:!1,busy:!1},this.store.host.requestUpdate()}closeSaveGroupModal(){this.store.saveGroupModal={...this.store.saveGroupModal,open:!1,busy:!1},this.store.host.requestUpdate()}async confirmSaveGroupModal(){let t=this.store.saveGroupModal.name.trim(),o=this.store.saveGroupModal.description.trim(),i=this.store.saveGroupModal.subentryId||this.store.activeSubentryId,a=!!this.store.saveGroupModal.includeDisplay,n=!!this.store.saveGroupModal.includeInterface;if(!t){this.store.showToast("Enter a Device group name",!0);return}if(!i){this.store.showToast("Choose a Device first",!0);return}this.store.saveGroupModal={...this.store.saveGroupModal,busy:!0},this.store.host.requestUpdate();try{let s={name:t,description:o,source_subentry_id:i,assign_source:!0};a&&(s.include_display=!0),n&&(s.include_interface=!0);let r=await this.store.ws.runSystemCommand("create_device_group",s,this.store.activeSubentryId||null);this.store.saveGroupModal={open:!1,subentryId:"",name:"",description:"",includeDisplay:!1,includeInterface:!1,busy:!1},r?this.store.ingestPayload(r,!1):this.store.host.requestUpdate(),this.store.showToast(`Saved custom group "${t}"`)}catch(s){this.store.saveGroupModal={...this.store.saveGroupModal,busy:!1},this.store.host.requestUpdate(),this.store.showToast(G(s,"Could not save custom Device group"),!0)}}async deleteDeviceGroup(t){let o=String(t||"").trim();if(o)try{let i=await this.store.ws.runSystemCommand("delete_device_group",{group_id:o},this.store.activeSubentryId||null);this.store.openGroupIds.delete(o),this.store.groupCopySourceDrafts.delete(o),this.store.batchTargetFilter===`group:${o}`&&(this.store.batchTargetFilter="all",this.resetBatchDraft()),i&&this.store.ingestPayload(i,!1),this.store.showToast("Deleted Device group")}catch(i){this.store.showToast(G(i,"Could not delete Device group"),!0)}}requestDeleteDeviceGroup(t,o,i){let a=String(t||"").trim();if(!a)return;let n=this.store.state?.device_groups?.find(c=>c.id===a),s=o||n?.name||a,r=i??(this.store.state?.system_devices||[]).filter(c=>c.kind!=="ble_tag"&&c.device_group===a).length;this.store.openConfirm({kind:"delete_group",title:this.store.t("confirm.delete_group.title",{name:s}),consequence:this.store.t("confirm.delete_group.body"),confirmLabel:this.store.t("confirm.delete_group.confirm"),danger:!0,blastRadiusCount:r>0?r:null,onConfirm:async()=>{await this.deleteDeviceGroup(a)}})}async resetDeviceGroupPreset(t,o){let i=String(t||"").trim();if(!i)return;let a=this.store.state?.device_groups?.find(s=>s.id===i),n=o||a?.name||i;try{let s=await this.store.ws.runSystemCommand("update_group_baseline",{group_id:i,reset_to_default:!0},this.store.activeSubentryId||null);s&&this.store.ingestPayload(s,!1),this.store.showToast(this.store.t("groups.reset_preset_toast",{name:n}))}catch(s){this.store.showToast(G(s,"Could not reset group preset"),!0)}}requestResetDeviceGroup(t,o,i){let a=String(t||"").trim();if(!a)return;let n=this.store.state?.device_groups?.find(c=>c.id===a),s=o||n?.name||a,r=i??(this.store.state?.system_devices||[]).filter(c=>c.kind!=="ble_tag"&&c.device_group===a).length;this.store.openConfirm({kind:"reset_group",title:this.store.t("confirm.reset_group.title",{name:s}),consequence:this.store.t("confirm.reset_group.body"),confirmLabel:this.store.t("confirm.reset_group.confirm"),danger:!1,blastRadiusCount:r>0?r:null,onConfirm:async()=>{await this.resetDeviceGroupPreset(a,s)}})}async updateGroupBaseline(t,o){if(t)try{let i=await this.store.ws.runSystemCommand("update_group_baseline",{group_id:t,config:o},this.store.activeSubentryId||null);i&&this.store.ingestPayload(i,!1),this.store.announcePolite(this.store.t("shell.saved_status"))}catch(i){this.store.showToast(G(i,"Could not update group baseline"),!0)}}async updateGroupScope(t,o){if(t)try{let i=await this.store.ws.runSystemCommand("update_group_baseline",{group_id:t,...o},this.store.activeSubentryId||null);i&&this.store.ingestPayload(i,!1),this.store.announcePolite(this.store.t("shell.saved_status"))}catch(i){this.store.showToast(G(i,"Could not update group scope"),!0)}}async copyDeviceToGroupBaseline(t,o,i){if(!t||!o){this.store.showToast("Choose a Device to copy settings from",!0);return}try{let a={group_id:t,source_subentry_id:o};i&&i.length&&(a.copy_keys=i);let n=await this.store.ws.runSystemCommand("update_group_baseline",a,this.store.activeSubentryId||null);n&&this.store.ingestPayload(n,!1),this.store.showToast("Copied Device settings into group baseline")}catch(a){this.store.showToast(G(a,"Could not copy Device settings"),!0)}}resolvedBatchTargetId(){return this.batch.resolvedBatchTargetId()}setBatchTargetFilter(t){this.batch.setBatchTargetFilter(t)}matchingBatchDevices(){return this.batch.matchingBatchDevices()}filteredControlTargets(t){return this.batch.filteredControlTargets(t)}getEffectiveBatchValue(t){return this.batch.getEffectiveBatchValue(t)}getEffectiveBatchPillStates(t){return this.batch.getEffectiveBatchPillStates(t)}stageBatchSetting(t,o){this.batch.stageBatchSetting(t,o)}stageBatchColor(t,o){this.batch.stageBatchColor(t,o)}stageBatchPillToggle(t,o,i){this.batch.stageBatchPillToggle(t,o,i)}resetBatchDraft(){this.batch.resetBatchDraft()}previewBatchDetachmentCount(){return this.batch.previewBatchDetachmentCount()}requestApplyBatchDraft(){this.batch.requestApplyBatchDraft()}async applyBatchDraft(){await this.batch.applyBatchDraft()}async applyBatchCopyFromDevice(t,o){await this.batch.applyBatchCopyFromDevice(t,o)}selectBleSurveyDevice(t){Ar(this.store,t)}selectBleCalibrateArea(t,o=!1){Er(this.store,t,o)}toggleBleLiveStream(t){Ir(this.store,t)}getActiveSurveyDevice(){return tn(this.store)}async setBleScannerOffset(t,o){await Pr(this.store,t,o)}async captureBleAreaSignature(t){await Mr(this.store,t)}async clearBleAreaSignature(t){await on(this.store,t)}requestClearBleAreaSignature(t,o){Dr(this.store,t,o)}async setAreaFusion(t,o){await Rr(this.store,t,o)}async setAreaIlluminance(t,o){await Lr(this.store,t,o)}async calibrateAreaIlluminance(t){await Or(this.store,this,t)}};function Br(e,t){let o=String(t||"").trim().toLowerCase();for(let[i,a]of Object.entries(e))if(a===o)return i;return null}function so(e,t,o){return e==="select_device_prompt"||e==="discovered_devices"||e==="dashboard"||e==="presence"||e==="tools"?!0:o==="ble_tag"?!1:t?e==="display"||e==="interface"?t.has_display!==!1:e==="audio_voice"?!(t.has_audio===!1&&t.has_voice===!1):e==="power"?t.has_power!==!1:!0:!0}function Nr(e,t){return e.state?.subentry_id!==e.activeSubentryId?e.state?.system_devices?.find(i=>i.subentry_id===e.activeSubentryId)?.kind==="ble_tag"?so(t,void 0,"ble_tag"):so(t,void 0,void 0):so(t,e.state?.capabilities,e.state?.config?.kind)}function xd(e,t){let o=e.scrollIntoView(t);if(o instanceof Promise)return o;let i=globalThis.window;return!i||typeof i.addEventListener!="function"?Promise.resolve():new Promise(a=>{let n,s=()=>{clearTimeout(n),i.removeEventListener("scrollend",s),i.removeEventListener("scroll",r),a()},r=()=>{clearTimeout(n),n=setTimeout(s,100)};i.addEventListener("scrollend",s,{once:!0}),i.addEventListener("scroll",r,{passive:!0}),n=setTimeout(s,100)})}function Hr(e,t){if(e.pendingDomRevert){let o=e.pendingDomRevert;e.pendingDomRevert=null;let i=e.host.renderRoot;if(i)for(let[a,n]of Object.entries(o.controlIds)){let s=i.getElementById(a);s&&(typeof n=="boolean"&&"checked"in s?s.checked=n:s.value=String(n))}}if(e.pendingScrollCardId){let o=e.pendingScrollCardId;e.pendingScrollCardId="";let a=(e.host.renderRoot||e.host.shadowRoot)?.getElementById(o);if(a&&typeof a.scrollIntoView=="function"){let n=++t.scrollGen,s=!!(typeof globalThis.matchMedia=="function"&&globalThis.matchMedia("(prefers-reduced-motion: reduce)").matches);xd(a,{behavior:s?"auto":"smooth",block:"start"}).then(()=>{if(!(n!==t.scrollGen||!e.handoffTargetIds.has(o))&&typeof a.focus=="function"){typeof a.hasAttribute=="function"&&!a.hasAttribute("tabindex")&&a.setAttribute?.("tabindex","-1");try{a.focus({preventScroll:!0})}catch{a.focus()}}})}}t.handoffArming=!1}function Ur(e,t,o="",i){let a=String(o||"").trim();e.pendingScrollCardId=a;let n=i&&i.length>0?i:a?[a]:[];for(let s of n){let r=String(s||"").trim();r&&e.handoffTargetIds.add(r)}e.handoffTargetIds.size>0&&(t.handoffArming=!0,e.host.requestUpdate())}function Fr(e,t,o){if(t.handoffArming||e.handoffTargetIds.size===0)return;let a=(typeof o.composedPath=="function"?o.composedPath():[])[0]??o.target;if(!a||typeof a.tagName!="string")return;let n=a.tagName.toUpperCase();if(n!=="BUTTON"&&n!=="INPUT"&&n!=="SELECT"&&n!=="TEXTAREA"&&n!=="SUMMARY"&&n!=="A")return;let s=a;for(;s;){if(s.id&&e.handoffTargetIds.has(s.id))return;s=s.parentElement}e.handoffTargetIds.clear(),e.host.requestUpdate()}function Vr(e,t,o,i){let a=String(t||"").trim(),n=String(o||"").trim();a&&a!==n&&(i?.discardPrevPending?e.entity.discardDeviceBucket(a):e.entity.flushDeviceBucket(a)),a!==n&&(e.devicePinDraft="",e.worldClockNewLabel="",e.worldClockNewZone="",e.worldClockRowKeys=[],e.overviewAlarmsOpen=!1,e.appConfigModal={open:!1,app:null},e.cameraConfigModal={...e.cameraConfigModal,open:!1},e.photoPickerModal=Mt(),e.shortcutModal={...e.shortcutModal,open:!1},e.saveGroupModal={...e.saveGroupModal,open:!1,busy:!1},e.resetModal={...e.resetModal,open:!1,busy:!1},e.removeModal={...e.removeModal,open:!1,busy:!1},e.returnToPinnedModal=!1,e.clearHandoffTargets()),e.activeSubentryId=n,e.deviceSelected=!!n,e.deviceLoading=!!(n&&e.state?.subentry_id!==n),e.syncLiveClockTimer()}function qr(e,t,o){let i=String(o?.path??"");if(!i&&!o&&typeof globalThis.location?.pathname=="string"){let d=globalThis.location.pathname;d.startsWith("/latter/")&&(i=d.slice(8))}let a=i.split("/").filter(Boolean).map(d=>{try{return decodeURIComponent(d)}catch{return d}}),n=e.currentScope,s=e.currentViewId,r=e.activeSubentryId,c=a[0],u=a[1],p=a[2];t.routeApplying=!0;try{if(c==="devices"&&u?.toLowerCase()==="discovered")n==="system"&&e.entity.flushSystemSettings(),e.onActiveDeviceChanged(r,""),(n!=="device"||s!=="discovered_devices")&&e.clearHandoffTargets(),e.currentScope="device",e.currentViewId="discovered_devices";else if(c==="devices"&&u){let d=u;if(e.state&&Array.isArray(e.state.system_devices)&&!e.state.system_devices.some(_=>_.subentry_id===d)){n==="system"&&e.entity.flushSystemSettings(),e.redirectInvalidDeviceRoute(d);return}n==="system"&&e.entity.flushSystemSettings();let m=Br(qt,p||"overview")||"dashboard";e.onActiveDeviceChanged(r,d);let g=e.deviceHasView(m)?m:"dashboard";(n!=="device"||s!==g||r!==d)&&e.clearHandoffTargets(),e.currentScope="device",e.currentViewId=g,g!==m&&_t(`/latter/devices/${encodeURIComponent(d)}/${qt[g]}`,!0)}else if(c==="system"){e.onActiveDeviceChanged(r,"");let d=Br(Gt,u||"overview")||"system_overview";n!=="system"||s!==d?e.clearHandoffTargets():d!=="area_tracking"&&(e.bleCalibrateHandoffActive=!1),e.currentScope="system",e.currentViewId=d,d==="area_tracking"&&e.ensureDefaultSurveyDevice()}else n==="system"&&e.entity.flushSystemSettings(),e.onActiveDeviceChanged(r,""),(n!=="device"||s!=="select_device_prompt")&&e.clearHandoffTargets(),e.currentScope="device",e.currentViewId="select_device_prompt";e.syncLiveClockTimer(),e.host.requestUpdate()}finally{t.routeApplying=!1}e.host.isConnected&&e.ws.hass&&!e.studioRevMismatch&&e.ensureSubscription(!1)}function Gr(e,t){let o=t??e.activeSubentryId;e.onActiveDeviceChanged(o,"",{discardPrevPending:!0}),e.currentScope="device",e.currentViewId="select_device_prompt",_t("/latter/devices",!0),o&&e.showToast(e.t("sync.device_not_found"),!1),e.host.requestUpdate(),e.host.isConnected&&e.ws.hass&&!e.studioRevMismatch&&e.ensureSubscription(!1)}function zr(e,t,o=!1){if(t.routeApplying)return;let i="/latter/devices";if(e.currentScope==="system")i=`/latter/system/${Gt[e.currentViewId]||"overview"}`;else if(e.currentViewId==="discovered_devices")i="/latter/devices/discovered";else if(e.deviceSelected&&e.activeSubentryId&&e.currentViewId!=="select_device_prompt"){let a=qt[e.currentViewId]||"overview";i=`/latter/devices/${encodeURIComponent(e.activeSubentryId)}/${a}`}globalThis.location?.pathname!==i&&_t(i,o)}function Kr(e){e.currentScope==="system"&&e.entity.flushSystemSettings(),e.onActiveDeviceChanged(e.activeSubentryId,""),e.clearHandoffTargets(),e.currentScope="device",e.currentViewId="select_device_prompt",e.syncLiveClockTimer(),e.syncUrl(),e.host.requestUpdate(),e.ensureSubscription(!1)}function Wr(e,t=""){e.currentScope==="system"&&e.entity.flushSystemSettings(),e.onActiveDeviceChanged(e.activeSubentryId,""),e.clearHandoffTargets(),e.currentScope="device",e.currentViewId="discovered_devices",e.syncLiveClockTimer(),e.syncUrl(),e.host.requestUpdate(),e.applySectionHandoff(t),e.ensureSubscription(!1)}function jr(e,t,o){t==="device"&&e.currentScope!=="device"?e.entity.flushSystemSettings():t==="system"&&e.onActiveDeviceChanged(e.activeSubentryId,""),e.clearHandoffTargets(),e.currentScope=t,o?e.currentViewId=o:t==="system"?e.currentViewId="system_overview":e.currentViewId=e.deviceSelected&&e.activeSubentryId?"dashboard":"select_device_prompt",e.currentViewId==="area_tracking"&&e.ensureDefaultSurveyDevice(),e.syncLiveClockTimer(),e.syncUrl(),e.host.requestUpdate(),e.ensureSubscription(!1)}function Yr(e,t){if(t==="select_device_prompt"){e.openDevicesLanding();return}if(t==="discovered_devices"){e.openDiscoveredDevices();return}e.clearHandoffTargets();let o=Object.prototype.hasOwnProperty.call(Gt,t);o?e.onActiveDeviceChanged(e.activeSubentryId,""):e.currentScope==="system"&&e.entity.flushSystemSettings(),e.currentScope=o?"system":"device",e.currentViewId=t,t==="area_tracking"&&e.ensureDefaultSurveyDevice(),e.syncLiveClockTimer(),e.syncUrl(),e.host.requestUpdate(),e.ensureSubscription(!1)}async function Zr(e,t,o="dashboard"){let i=String(t||"").trim();if(!i)return;e.currentScope==="system"&&e.entity.flushSystemSettings(),e.onActiveDeviceChanged(e.activeSubentryId,i),e.currentScope="device";let a=o==="select_device_prompt"||o==="discovered_devices"?"dashboard":o;e.currentViewId=e.deviceHasView(a)?a:"dashboard",e.syncLiveClockTimer(),e.syncUrl(),e.host.requestUpdate(),await e.ensureSubscription(!1)}function Xr(e,t=!1){let o=e.state?.links,i=t?o?.latter_device_id||o?.esphome_device_id||"":o?.esphome_device_id||o?.latter_device_id||"";i?_t(`/config/devices/device/${encodeURIComponent(i)}`,!1):_t("/config/integrations/integration/latter",!1)}var Jr=[2e3,5e3,15e3,6e4],Di=class{store;subGen=0;stateReqSeq=0;lastAppliedReqSeq=0;wsUnsub=null;subscribedKey="";reconnectTimer=null;reconnectAttempt=0;boundConnection=null;onConnectionReady=()=>{this.store.studioRevMismatch||!this.store.host.isConnected||(this.reconnectAttempt=0,this.clearReconnectTimer(),this.store.ensureSubscription(!0))};constructor(t){this.store=t}clearReconnectTimer(){this.reconnectTimer&&(clearTimeout(this.reconnectTimer),this.reconnectTimer=null)}syncConnectionListener(){let t=this.store.host.isConnected?this.store.ws.hass?.connection??null:null;this.boundConnection!==t&&(this.detachConnectionListener(),t&&typeof t.addEventListener=="function"&&(t.addEventListener("ready",this.onConnectionReady),this.boundConnection=t))}detachConnectionListener(){if(this.boundConnection&&typeof this.boundConnection.removeEventListener=="function")try{this.boundConnection.removeEventListener("ready",this.onConnectionReady)}catch{}this.boundConnection=null}teardownSubscription(){if(this.subGen+=1,typeof this.wsUnsub=="function")try{this.wsUnsub()}catch{}this.wsUnsub=null,this.subscribedKey=""}desiredSubscriptionKey(){let t=this.store.deviceSelected&&this.store.activeSubentryId||"",o=this.store.currentScope==="system"&&this.store.currentViewId==="area_tracking"&&this.store.bleLiveStreamActive&&this.store.bleSurveySubentryId||"",i=this.store.shouldIncludeLogs()?"1":"0";return`${t}|${o}|${i}`}async ensureSubscription(t=!1){if(this.store.studioRevMismatch||!this.store.ws.hass?.connection)return;let o=this.store.desiredSubscriptionKey();if(!t&&this.wsUnsub&&this.subscribedKey===o)return;this.clearReconnectTimer(),this.store.teardownSubscription();let i=++this.subGen,a=this.store.deviceSelected&&this.store.activeSubentryId||null,n=this.store.currentScope==="system"&&this.store.currentViewId==="area_tracking"&&this.store.bleLiveStreamActive&&this.store.bleSurveySubentryId||null,s=this.store.shouldIncludeLogs();try{let r=await this.store.ws.subscribe({subentryId:a,surveySubentryId:n,includeLogs:s},c=>{i!==this.subGen||!c||this.handleSubscriptionEvent(c,s)});if(i!==this.subGen){try{r()}catch{}return}this.wsUnsub=r,this.subscribedKey=o,this.reconnectAttempt=0}catch(r){if(Oo(r)||this.store.studioRevMismatch){this.store.handleStudioRevMismatch();return}this.store.state?this.store.deviceLoading&&(this.store.deviceLoading=!1,this.store.loadError=G(r,"Latter Studio could not connect."),this.store.host.requestUpdate()):(this.store.loading=!1,this.store.deviceLoading=!1,this.store.loadError=G(r,"Latter Studio could not connect."),this.store.host.requestUpdate());let c=Jr[Math.min(this.reconnectAttempt,Jr.length-1)]??6e4;this.reconnectAttempt+=1,this.clearReconnectTimer(),this.reconnectTimer=setTimeout(()=>{this.reconnectTimer=null,this.store.host.isConnected&&!this.store.studioRevMismatch&&this.store.ensureSubscription(!0)},c)}}async refreshState(t){if(this.store.studioRevMismatch||!this.store.ws.hass)return;let o=++this.stateReqSeq,i=this.store.deviceSelected&&this.store.activeSubentryId||null,a=t?.includeLogs??this.store.shouldIncludeLogs();try{let n=await this.store.ws.getState({subentryId:i,includeLogs:a});if(o<this.lastAppliedReqSeq)return;this.lastAppliedReqSeq=o,this.store.loadError="",this.store.loading=!1,this.store.ingestPayload(n,a),!this.wsUnsub&&this.store.host.isConnected&&!this.store.studioRevMismatch&&this.store.ensureSubscription(!1)}catch(n){if(Oo(n)||this.store.studioRevMismatch){this.store.handleStudioRevMismatch();return}if(o<this.lastAppliedReqSeq)return;this.store.loading=!1,this.store.deviceLoading=!1,this.store.loadError=G(n,"Latter Studio could not load."),this.store.host.requestUpdate()}}handleSubscriptionEvent(t,o){if(!t||typeof t!="object")return;let i=t;if(i.type==="ble_survey_delta"){this.store.applyBleSurveyDelta(i);return}let a=t;this.store.loading=!1,this.store.loadError="",this.store.ingestPayload(a,o)}applyBleSurveyDelta(t){if(!this.store.state)return;if(!this.store.bleLiveStreamActive){let n=!1;Array.isArray(t.ble_area_signatures)&&(this.store.state={...this.store.state,ble_area_signatures:t.ble_area_signatures},n=!0),Array.isArray(t.area_presence_grid)&&this.store.state.live&&(this.store.state={...this.store.state,live:{...this.store.state.live,area_presence_grid:t.area_presence_grid}},n=!0),n&&this.store.host.requestUpdate();return}let o=String(t.subentry_id||this.store.bleSurveySubentryId||this.store.state.subentry_id||""),i=this.store.state.system_devices,a=this.store.state.live;if(Array.isArray(t.ble_survey_rows)){let n=t.ble_survey_rows,s=n.find(r=>r.is_winner);Array.isArray(i)&&o&&(i=i.map(r=>r.subentry_id!==o?r:{...r,ble_survey_rows:n,ble_packets_seen:typeof t.ble_packets_seen=="number"?t.ble_packets_seen:r.ble_packets_seen,active_area_name:s?.area_name||r.active_area_name})),this.store.state.subentry_id===o&&a&&typeof t.ble_closest_proxy=="string"&&(a={...a,ble_closest_proxy:t.ble_closest_proxy})}Array.isArray(t.area_presence_grid)&&a&&(a={...a,area_presence_grid:t.area_presence_grid}),this.store.state={...this.store.state,system_devices:i,ble_area_signatures:Array.isArray(t.ble_area_signatures)?t.ble_area_signatures:this.store.state.ble_area_signatures,live:a},this.store.host.requestUpdate()}mergeFrozenBleRows(t){return this.store.bleLiveStreamActive||!Array.isArray(t)?t:t.map(o=>{if(!o.subentry_id)return o;let i=this.store.bleSurveyFrozen.get(o.subentry_id);return i?{...o,ble_survey_rows:i.rows.map(a=>({...a})),ble_packets_seen:i.packetsSeen,active_area_name:i.activeAreaName}:(this.store.bleSurveyFrozen.set(o.subentry_id,{rows:(o.ble_survey_rows||[]).map(a=>({...a})),packetsSeen:o.ble_packets_seen??0,activeAreaName:o.active_area_name||""}),o)})}ingestPayload(t,o){let i=this.store.state,a=i?.system_config,n=t.catalog??i?.catalog,s=t.pref_specs??i?.pref_specs,r=t.world_clock_zones??i?.world_clock_zones,c=t.system_wallpapers??i?.system_wallpapers??[],u=t.photo_collections??i?.photo_collections??[],p=t.ble_area_signatures??i?.ble_area_signatures,d=t.discovered_ble_devices!==void 0?this.stabilizeDiscoveredBle(t.discovered_ble_devices,t.system_devices):i?.discovered_ble_devices??[],m=o||Array.isArray(t.internal_logs)&&t.internal_logs.length>0?t.internal_logs||[]:i?.internal_logs||[],g=this.mergeFrozenBleRows(t.system_devices);if(t.subentry_id&&t.device_config_rev>0&&this.store.recordKnownDeviceConfigRev(t.subentry_id,t.device_config_rev),this.store.deviceSelected&&this.store.activeSubentryId&&Array.isArray(g)&&!g.some(b=>b.subentry_id===this.store.activeSubentryId)){let b={...t,system_devices:g,discovered_ble_devices:d,photo_collections:u,system_wallpapers:c,ble_area_signatures:p,catalog:n,pref_specs:s,world_clock_zones:r,internal_logs:m,device_prefs:t.device_prefs||[]},y=this.store.entity.getEffectiveSystemPatch();Object.keys(y).length>0&&b.system_config&&(b.system_config={...b.system_config,...y}),to(this.store,b,a),this.store.state=b,this.store.redirectInvalidDeviceRoute(this.store.activeSubentryId);return}if(this.store.deviceSelected&&this.store.activeSubentryId&&t.subentry_id!==this.store.activeSubentryId){let b=i&&i.subentry_id===this.store.activeSubentryId,y={...b?i:t,version:t.version,studio_rev:t.studio_rev??i?.studio_rev,system_config_rev:t.system_config_rev,system_info:t.system_info??i?.system_info,locale_strings:t.locale_strings??i?.locale_strings,internal_logs:m,system_devices:g,issues:t.issues,ble_proxy_count:t.ble_proxy_count,ble_area_signatures:p,discovered_latter_devices:t.discovered_latter_devices,ignored_latter_devices:t.ignored_latter_devices??i?.ignored_latter_devices,discovered_ble_devices:d,system_controls:t.system_controls,device_groups:t.device_groups,system_config:t.system_config,has_security_pin:t.has_security_pin,photo_collections:u,system_wallpapers:c,catalog:n,pref_specs:s,world_clock_zones:r,subentry_id:b?i.subentry_id:"",title:b?i.title:"",device_config_rev:b?i.device_config_rev:0,capabilities:b?i.capabilities:{},config:b?i.config:{},device_prefs:b?i.device_prefs:[],quick_actions:b?i.quick_actions:[],speaker_volume:b?i.speaker_volume:null,esphome:b?i.esphome:{device:{},sections:[]},wallpapers:b?i.wallpapers:[],links:b?i.links:void 0,live:b?{...i.live,area_presence_grid:t.live?.area_presence_grid??i.live.area_presence_grid}:{area_presence_grid:t.live?.area_presence_grid}},f=this.store.entity.getEffectiveSystemPatch();Object.keys(f).length>0&&y.system_config&&(y.system_config={...y.system_config,...f}),to(this.store,y,a),this.store.deviceLoading=!b,this.store.state=y,this.store.ensureDefaultSurveyDevice(),this.store.ensureDefaultDoorbellTester(),this.store.ensureValidBatchTargetFilter(),this.store.syncLiveClockTimer(),this.store.host.requestUpdate(),!b&&this.store.host.isConnected&&this.store.ws.hass&&!this.store.studioRevMismatch&&this.store.ensureSubscription(!1);return}this.store.deviceLoading=!1;let _={...t,system_devices:g,discovered_ble_devices:d,photo_collections:u,system_wallpapers:c,ble_area_signatures:p,catalog:n,pref_specs:s,world_clock_zones:r,internal_logs:m,device_prefs:t.device_prefs||[]},h=this.store.entity.getEffectiveSystemPatch();if(Object.keys(h).length>0&&_.system_config&&(_.system_config={..._.system_config,...h}),to(this.store,_,a),_.subentry_id){let b=this.store.entity.getEffectiveDevicePatch(_.subentry_id);Object.keys(b).length>0&&_.config&&Dt(_,b)}No(_,this.store.pendingEntityStates),this.store.currentScope==="device"&&this.store.deviceSelected&&_.subentry_id===this.store.activeSubentryId&&!so(this.store.currentViewId,_.capabilities,_.config?.kind)&&(this.store.currentViewId="dashboard",this.store.syncUrl(!0)),this.store.state=_,this.store.ensureDefaultSurveyDevice(),this.store.ensureDefaultDoorbellTester(),this.store.ensureValidBatchTargetFilter(),this.store.syncLiveClockTimer(),this.store.host.requestUpdate()}stabilizeDiscoveredBle(t,o){let a=Date.now(),n=new Set((o||[]).map(r=>String(r.device_slug||"").trim().toLowerCase()).filter(Boolean));for(let[r,c]of this.store.discoveredBleSeenCache.entries()){let u=String(c.candidate.slug||"").trim().toLowerCase();(a-c.lastSeenMs>9e4||u&&n.has(u))&&this.store.discoveredBleSeenCache.delete(r)}let s=[];for(let r of t){let c=String(r.target_address||"").trim().toLowerCase();c?this.store.discoveredBleSeenCache.set(c,{candidate:r,lastSeenMs:a}):s.push(r)}return[...Array.from(this.store.discoveredBleSeenCache.values(),r=>r.candidate),...s]}toggleDiscoveredBlePause(t){let o=t??!this.store.discoveredBlePaused;this.store.discoveredBlePaused=o,o?this.store.discoveredBleFrozenSnapshot=[...this.store.state?.discovered_ble_devices||[]]:this.store.discoveredBleFrozenSnapshot=null,this.store.host.requestUpdate()}evictAdoptedBleCandidate(t){let o=String(t||"").trim().toLowerCase();o&&(this.store.discoveredBleSeenCache.delete(o),this.store.discoveredBlePersonDrafts.delete(o),this.store.discoveredBleFrozenSnapshot&&(this.store.discoveredBleFrozenSnapshot=this.store.discoveredBleFrozenSnapshot.filter(i=>String(i.target_address||"").trim().toLowerCase()!==o)))}ensureDefaultSurveyDevice(){let o=(this.store.state?.system_devices||[]).filter(a=>a.ble_tracked||a.kind==="ble_tag");if(this.store.bleSurveySubentryId&&o.some(a=>a.subentry_id===this.store.bleSurveySubentryId))return;let i=o.find(a=>a.subentry_id===this.store.activeSubentryId);this.store.bleSurveySubentryId=i?.subentry_id||o[0]?.subentry_id||""}ensureDefaultDoorbellTester(){let t=(this.store.state?.system_devices||[]).filter(o=>o.kind!=="ble_tag");this.store.doorbellTestSubentryId&&t.some(o=>o.subentry_id===this.store.doorbellTestSubentryId)||(this.store.doorbellTestSubentryId=t[0]?.subentry_id||"")}ensureValidBatchTargetFilter(){if(!this.store.batchTargetFilter.startsWith("group:"))return;let t=this.store.batchTargetFilter.slice(6);if(t==="custom")return;(this.store.state?.device_groups||[]).some(i=>i.id===t)||(this.store.batchTargetFilter="all",this.store.groups.resetBatchDraft())}};var Ri=class{store;constructor(t){this.store=t}openConfirm(t){this.store.confirmModal={open:!0,kind:t.kind||"confirm",title:t.title,consequence:t.consequence,confirmLabel:t.confirmLabel,cancelLabel:t.cancelLabel||this.store.t("action.cancel"),danger:t.danger!==!1,blastRadiusCount:t.blastRadiusCount??null,blastRadiusLabel:t.blastRadiusLabel||"",busy:!1,onConfirm:t.onConfirm,onDownloadBackupFirst:t.onDownloadBackupFirst??null},this.store.host.requestUpdate()}closeConfirm(){this.store.confirmModal.busy||(this.store.confirmModal=Bo(),this.store.host.requestUpdate())}async runConfirmedAction(){let t=this.store.confirmModal.onConfirm;if(!(!t||this.store.confirmModal.busy)){this.store.confirmModal={...this.store.confirmModal,busy:!0},this.store.host.requestUpdate();try{await t(),this.store.confirmModal=Bo()}finally{this.store.confirmModal.busy&&(this.store.confirmModal={...this.store.confirmModal,busy:!1}),this.store.host.requestUpdate()}}}async saveSecurityPin(t){let o=(t==="device"?this.store.devicePinDraft:this.store.systemPinDraft).trim();if(!/^\d{4,12}$/.test(o)){this.store.showToast("Security PIN must be 4 to 12 digits",!0);return}let i=t==="device"?this.store.activeSubentryId:"";this.store.pinBusy=!0,this.store.host.requestUpdate();try{let a={pin:o};i&&(a.subentry_id=i);let n=await this.store.ws.runSystemCommand("set_security_pin",a,this.store.activeSubentryId||null);this.store.devicePinDraft="",this.store.systemPinDraft="",n&&this.store.ingestPayload(n,!1),this.store.showToast("Saved security PIN")}catch(a){this.store.showToast(G(a,"Could not save security PIN"),!0)}finally{this.store.pinBusy=!1,this.store.host.requestUpdate()}}async clearSecurityPin(t){let o=t==="device"?this.store.activeSubentryId:"";this.store.pinBusy=!0,this.store.host.requestUpdate();try{let i={clear:!0};o&&(i.subentry_id=o);let a=await this.store.ws.runSystemCommand("set_security_pin",i,this.store.activeSubentryId||null);this.store.devicePinDraft="",this.store.systemPinDraft="",a&&this.store.ingestPayload(a,!1),this.store.showToast("Cleared security PIN")}catch(i){this.store.showToast(G(i,"Could not clear security PIN"),!0)}finally{this.store.pinBusy=!1,this.store.host.requestUpdate()}}requestClearSecurityPin(t){let o=t==="system"?(this.store.state?.system_devices||[]).filter(i=>i.kind!=="ble_tag").length:1;this.openConfirm({kind:"clear_pin",title:this.store.t("confirm.clear_pin.title"),consequence:this.store.t("confirm.clear_pin.body"),confirmLabel:this.store.t("confirm.clear_pin.confirm"),danger:!0,blastRadiusCount:o>0?o:null,onConfirm:async()=>{await this.clearSecurityPin(t)}})}async rotateSigningKey(){try{let t=await this.store.ws.runSystemCommand("rotate_signing_key",{},this.store.activeSubentryId||null);this.store.entity.clearCameraPreviewCache(),t&&this.store.ingestPayload(t,!1),this.store.showToast("Rotated HTTP resource signing key")}catch(t){this.store.showToast(G(t,"Could not rotate signing key"),!0)}}requestRotateSigningKey(){let t=(this.store.state?.system_devices||[]).filter(o=>o.kind!=="ble_tag").length;this.openConfirm({kind:"rotate_signing_key",title:this.store.t("confirm.rotate_signing_key.title"),consequence:this.store.t("confirm.rotate_signing_key.body"),confirmLabel:this.store.t("confirm.rotate_signing_key.confirm"),danger:!0,blastRadiusCount:t>0?t:null,onConfirm:async()=>{await this.rotateSigningKey()}})}async resolveConfigEntryId(){let t=this.store.state?.links?.entry_id||"";if(t)return t;let o=this.store.hass;if(!o)return"";try{let i=await o.callWS({type:"config_entries/get",domain:"latter"});return String(i?.[0]?.entry_id||"")}catch{return""}}async triggerSignedPathDownload(t){let o=await this.store.ws.signHaPath(t,300),i=document.createElement("a");i.href=o,i.download="",document.body.appendChild(i),i.click(),document.body.removeChild(i)}async downloadDeviceDiagnostics(){let t=await this.resolveConfigEntryId(),o=this.store.state?.links?.latter_device_id||"";if(!t){this.store.showToast("Diagnostics entry ID is not available",!0);return}let i=o?`/api/diagnostics/config_entry/${encodeURIComponent(t)}/device/${encodeURIComponent(o)}`:`/api/diagnostics/config_entry/${encodeURIComponent(t)}`;try{await this.triggerSignedPathDownload(i)}catch(a){this.store.showToast(G(a,"Could not download diagnostics"),!0)}}async downloadSystemDiagnostics(){let t=await this.resolveConfigEntryId();if(!t){this.store.showToast("Diagnostics entry ID is not available",!0);return}let o=`/api/diagnostics/config_entry/${encodeURIComponent(t)}`;try{await this.triggerSignedPathDownload(o)}catch(i){this.store.showToast(G(i,"Could not download System diagnostics"),!0)}}formatSystemInfoSummary(){let t=this.store.state?.system_info,o=t?.ha_version||this.store.hass?.config?.version||"\u2014",i=t?.integration_version||this.store.state?.version||"\u2014",a=t?.min_firmware_sdk_rev?String(t.min_firmware_sdk_rev):"\u2014",n=String(t?.studio_rev??46),s=this.store.state?.system_devices||[],r=s.filter(u=>u.kind!=="ble_tag").length,c=s.filter(u=>u.kind==="ble_tag").length;return[`Home Assistant: ${o}`,`Latter integration: v${i}`,`Minimum firmware SDK: ${a}`,`Studio contract: rev ${n}`,`Managed Devices: ${s.length} (${r} displays, ${c} BLE trackers)`].join(`
`)}async copySystemInfoSummary(){let t=this.store.host.renderRoot||this.store.host.shadowRoot,o=await Ia(this.formatSystemInfoSummary(),t);this.store.showToast(o?this.store.t("support.copied_summary"):"Could not copy version summary",!o)}openColorWheelModal(t){let o=t==="device"&&ue(this.store.state?.config?.device_custom_color)?String(this.store.state?.config?.device_custom_color).toUpperCase():Eo(this.store.host);this.store.colorWheelModal={open:!0,targetScope:t,hex:o,name:"",busy:!1,painted:this.store.colorWheelModal.painted},this.store.host.requestUpdate()}closeColorWheelModal(){this.store.colorWheelModal={...this.store.colorWheelModal,open:!1,busy:!1},this.store.host.requestUpdate()}async saveColorWheelSelection(){let t=this.store.colorWheelModal.hex.trim().toUpperCase();if(!ue(t)){this.store.showToast("Enter a valid 6-digit hex color",!0);return}this.store.colorWheelModal={...this.store.colorWheelModal,busy:!0},this.store.host.requestUpdate();try{let o=this.store.colorWheelModal.name.trim()||t,i=[...this.store.state?.system_config?.custom_palettes||[]];i.some(a=>a.hex.toUpperCase()===t)||(i.push({name:o,hex:t}),this.store.entity.stageSystemSetting("custom_palettes",i),await this.store.entity.flushSystemSettings()),this.store.colorWheelModal.targetScope==="device"&&this.store.activeSubentryId&&(this.store.entity.applyDeviceCustomColor(t,!0),await this.store.entity.flushDeviceBucket(this.store.activeSubentryId)),this.closeColorWheelModal()}finally{this.store.colorWheelModal.busy&&(this.store.colorWheelModal={...this.store.colorWheelModal,busy:!1},this.store.host.requestUpdate())}}openRemoveDeviceModal(t,o){t&&(this.store.removeModal={open:!0,subentryId:t,title:o||"Device",busy:!1},this.store.host.requestUpdate())}closeRemoveDeviceModal(){this.store.removeModal={...this.store.removeModal,open:!1,busy:!1},this.store.host.requestUpdate()}async removeDeviceById(t){let o=String(t||"").trim();if(o)try{this.store.entity.discardDeviceBucket(o);let i=await this.store.ws.runSystemCommand("remove_device",{subentry_id:o},this.store.activeSubentryId||null);this.closeRemoveDeviceModal(),this.store.activeSubentryId===o&&(this.store.onActiveDeviceChanged(o,"",{discardPrevPending:!0}),this.store.currentScope="device",this.store.currentViewId="select_device_prompt",this.store.syncUrl(!0)),i&&this.store.ingestPayload(i,!1),this.store.showToast("Removed Device from Latter")}catch(i){throw this.store.showToast(G(i,"Could not remove Device"),!0),i}}async confirmRemoveDevice(){let t=this.store.removeModal.subentryId;if(t){this.store.removeModal={...this.store.removeModal,busy:!0},this.store.host.requestUpdate();try{await this.removeDeviceById(t)}catch{this.store.removeModal={...this.store.removeModal,busy:!1},this.store.host.requestUpdate()}}}requestRemoveDevice(t,o){let i=String(t||"").trim();if(!i)return;let a=o||"Device";this.openConfirm({kind:"remove_device",title:this.store.t("confirm.remove_device.title",{title:a}),consequence:this.store.t("confirm.remove_device.body",{title:a}),confirmLabel:this.store.t("confirm.remove_device.confirm"),danger:!0,blastRadiusCount:1,onDownloadBackupFirst:()=>{this.exportBackup(i)},onConfirm:async()=>{await this.removeDeviceById(i)}})}openResetDeviceModal(){if(!this.store.activeSubentryId)return;let t=this.store.state?.config?.kind==="ble_tag";this.store.resetModal={open:!0,deviceSettings:!t,latterOptions:!0,busy:!1},this.store.host.requestUpdate()}closeResetDeviceModal(){this.store.resetModal={...this.store.resetModal,open:!1,busy:!1},this.store.host.requestUpdate()}async confirmResetDevice(){let t=this.store.activeSubentryId;if(t&&!(!this.store.resetModal.deviceSettings&&!this.store.resetModal.latterOptions)){this.store.resetModal={...this.store.resetModal,busy:!0},this.store.host.requestUpdate();try{this.store.entity.discardDeviceBucket(t);let o=await this.store.ws.resetDevice({subentryId:t,deviceSettings:this.store.resetModal.deviceSettings,latterOptions:this.store.resetModal.latterOptions});this.closeResetDeviceModal(),o&&this.store.activeSubentryId===t&&this.store.ingestPayload(o,!1),this.store.showToast("Reset Device to defaults")}catch(o){this.store.resetModal={...this.store.resetModal,busy:!1},this.store.showToast(G(o,"Could not reset Device"),!0),this.store.host.requestUpdate()}}}openAddBleModal(t){this.store.addBleModal={open:!0,candidateAddr:t?.address||"",name:t?.name||"",address:t?.address||"",assignedPerson:"",bleCategory:"auto",busy:!1},this.store.host.requestUpdate()}closeAddBleModal(){this.store.addBleModal={...this.store.addBleModal,open:!1,busy:!1},this.store.host.requestUpdate()}selectBleCandidateInModal(t){let o=(this.store.state?.discovered_ble_devices||[]).find(n=>n.target_address===t),i=o&&o.target_address||t,a=o&&o.title||"";this.store.addBleModal={...this.store.addBleModal,candidateAddr:t,address:o?i:this.store.addBleModal.address,name:a||this.store.addBleModal.name},this.store.host.requestUpdate()}async adoptLatterDevice(t,o,i="auto",a=""){if(t)try{let n=await this.store.ws.runSystemCommand("add_latter_device",{esphome_device_id:t,device_group:i||"auto",assigned_person:a},this.store.activeSubentryId||null);this.store.discoveredLatterGroupDrafts.delete(t),this.store.discoveredLatterPersonDrafts.delete(t),n&&(this.store.ingestPayload(n,!1),n.adopted_subentry_id&&await this.store.switchSystemDevice(n.adopted_subentry_id,"dashboard")),this.store.showToast(this.store.t("discovered.adopted_toast",{title:o||"Device"}))}catch(n){this.store.showToast(G(n,"Could not adopt Latter Device"),!0)}}async ignoreDiscoveredDevice(t,o){let i=String(t||"").trim();if(i)try{let a=await this.store.ws.runSystemCommand("ignore_discovered_device",{esphome_device_id:i},this.store.activeSubentryId||null);a&&this.store.ingestPayload(a,!1),this.store.showToast(this.store.t("discovered.ignored_toast",{title:o||i}))}catch(a){this.store.showToast(G(a,"Could not ignore discovered Device"),!0)}}async unignoreDiscoveredDevice(t,o){let i=String(t||"").trim();if(i)try{let a=await this.store.ws.runSystemCommand("unignore_discovered_device",{esphome_device_id:i},this.store.activeSubentryId||null);a&&this.store.ingestPayload(a,!1),this.store.showToast(this.store.t("discovered.restored_toast",{title:o||i}))}catch(a){this.store.showToast(G(a,"Could not restore discovered Device"),!0)}}async quickAdoptBleCandidate(t,o,i="",a="auto"){if(!(!t||!o))try{let n=await this.store.ws.runSystemCommand("add_ble_device",{name:t,target_address:o,assigned_person:i,ble_category:a||"auto"},this.store.activeSubentryId||null);this.store.evictAdoptedBleCandidate(o),n&&(this.store.ingestPayload(n,!1),n.adopted_subentry_id&&await this.store.switchSystemDevice(n.adopted_subentry_id,"dashboard")),this.store.showToast(this.store.t("discovered.adopted_toast",{title:t}))}catch(n){this.store.showToast(G(n,"Could not add BLE tag"),!0)}}async confirmAddBleModal(){let t=this.store.addBleModal.name.trim(),o=this.store.addBleModal.address.trim();if(!t||!o){this.store.showToast("Enter both a name and a Bluetooth address or entity",!0);return}this.store.addBleModal={...this.store.addBleModal,busy:!0},this.store.host.requestUpdate();try{let i=await this.store.ws.runSystemCommand("add_ble_device",{name:t,target_address:o,assigned_person:this.store.addBleModal.assignedPerson,ble_category:this.store.addBleModal.bleCategory||"auto"},this.store.activeSubentryId||null);this.store.evictAdoptedBleCandidate(o),this.closeAddBleModal(),i&&(this.store.ingestPayload(i,!1),i.adopted_subentry_id&&await this.store.switchSystemDevice(i.adopted_subentry_id,"dashboard")),this.store.showToast(this.store.t("discovered.adopted_toast",{title:t}))}catch(i){this.store.addBleModal={...this.store.addBleModal,busy:!1},this.store.showToast(G(i,"Could not add BLE tag"),!0),this.store.host.requestUpdate()}}async checkSystemUpdates(){this.store.showToast("Checking firmware updates\u2026");try{let t=await this.store.ws.runSystemCommand("check_system_updates",{},this.store.activeSubentryId||null);if(t){this.store.ingestPayload(t,!1);let o=t.update_check;if(o){this.store.showToast(o.available>0?`${o.available} firmware update(s) available across ${o.checked} checked Device(s)`:`Checked ${o.checked} Device(s) \u2014 all firmware is up to date`);return}}this.store.showToast("Firmware update check finished")}catch(t){this.store.showToast(G(t,"Firmware update check failed"),!0)}}async sendAnnouncement(){let t=this.store.announceMessage.trim();if(!t){this.store.showToast("Enter a message",!0);return}let o={mode:this.store.announceMode,target_device:this.store.announceTarget||"all",message:t};if(this.store.announceMode==="notify"){let i=this.store.announceTitle.trim();if(!i){this.store.showToast("Enter a notification title",!0);return}o.title=i,o.priority=this.store.announcePriority,o.include_camera=this.store.announceIncludeCamera}try{let i=await this.store.ws.runSystemCommand("send_announcement",o,this.store.activeSubentryId||null);i&&this.store.ingestPayload(i,!1),this.store.showToast(this.store.announceMode==="notify"?"Sent notification":"Broadcast announcement sent")}catch(i){this.store.showToast(G(i,"Could not send announcement"),!0)}}async exportBackup(t){try{let o=new Date().toISOString().slice(0,10);if(t){let{bundle:n}=await this.store.ws.exportBackup("device",t),s=String(n.target_device||this.store.state?.config?.device_slug||"esphome");pi(`latter-device-${s}-backup-${o}.json`,n),this.store.showToast("Downloaded the Device backup");return}let i=this.store.backupExportScope||"system",a=i.startsWith("device:")?i.slice(7):i!=="system"?i:"";if(a){let{bundle:n}=await this.store.ws.exportBackup("device",a),s=String(n.target_device||a);pi(`latter-device-${s}-backup-${o}.json`,n),this.store.showToast("Downloaded the Device backup")}else{let{bundle:n}=await this.store.ws.exportBackup("system");pi(`latter-system-backup-${o}.json`,n),this.store.showToast("Downloaded the System backup")}}catch(o){this.store.showToast(G(o,"Backup export failed"),!0)}}async parseBackupBundleFile(){if(!this.store.selectedBackupFile)return this.store.showToast("Choose a JSON backup file first",!0),null;let t=await this.store.selectedBackupFile.text(),o=JSON.parse(t);if(!o||typeof o!="object"||Array.isArray(o))throw new Error("Invalid backup JSON format");let i=o,a=String(i.scope||"");if(a!=="system"&&a!=="device")throw new Error("Backup file is missing a valid 'system' or 'device' scope");let n=a,s=n==="device"&&this.store.backupRestoreSubentryId||"";return n==="device"&&!s?(this.store.showToast("Choose the Device to restore this Device backup onto",!0),null):{bundle:i,scope:n,targetId:s}}async restoreFromUploadedFile(){try{let t=await this.parseBackupBundleFile();if(!t)return;let{bundle:o,scope:i,targetId:a}=t,n=await this.store.ws.importBackup({scope:i,bundle:o,targetSubentryId:a||null,selectedSubentryId:this.store.activeSubentryId||null});this.store.selectedBackupFile=null,this.store.mergeDomRevert({"input-restore-backup":""}),n&&this.store.ingestPayload(n,!1),this.store.showToast(i==="device"?"Restored the Device backup":"Restored the System backup")}catch(t){this.store.showToast(G(t,"Backup restore failed"),!0)}}async requestRestoreFromUploadedFile(){try{let t=await this.parseBackupBundleFile();if(!t)return;let{scope:o,targetId:i}=t,a=o==="device"?1:Math.max(1,(this.store.state?.system_devices||[]).length);this.openConfirm({kind:"restore_backup",title:this.store.t("confirm.restore_backup.title"),consequence:this.store.t("confirm.restore_backup.body"),confirmLabel:this.store.t("confirm.restore_backup.confirm"),danger:!0,blastRadiusCount:a,onDownloadBackupFirst:()=>{this.exportBackup(o==="device"?i:void 0)},onConfirm:async()=>{await this.restoreFromUploadedFile()}})}catch(t){this.store.showToast(G(t,"Backup restore failed"),!0)}}onToggleLogsDetails(t){this.store.logsOpen!==t&&(this.store.logsOpen=t,this.store.host.requestUpdate(),this.store.ensureSubscription(!1))}formatVisibleLogs(){let t=this.store.state?.internal_logs||[],o=this.store.logFilter||"all",i=t.filter(a=>{let n=String(a.level||"").toUpperCase(),s=String(a.source||"").toLowerCase();if(o==="latter")return s==="studio"||s==="system"||s.includes("latter");if(o==="errors")return n==="WARNING"||n==="WARN"||n==="ERROR"||n==="CRITICAL";if(o.startsWith("device:")){let r=o.slice(7).toLowerCase();return s===r||String(a.message||"").toLowerCase().includes(r)}return!0});return i.length?i.map(a=>{let n=a.timestamp??a.ts??"",s=n!==""?ci(n,this.store.hass):"",r=String(a.level||"INFO").toUpperCase(),c=String(a.source||"latter");return`${s?`[${s}] `:""}${r} (${c}): ${String(a.message||"")}`}).join(`
`):"No events logged yet."}async copyLogsToClipboard(){let t=this.store.host.renderRoot||this.store.host.shadowRoot,o=await Ia(this.formatVisibleLogs(),t);this.store.showToast(o?"Copied logs to clipboard":"Could not copy logs",!o)}async clearInternalLogs(){try{let t=await this.store.ws.runSystemCommand("clear_internal_logs",{},this.store.activeSubentryId||null);t&&this.store.ingestPayload(t,!0),this.store.showToast("Cleared internal logs")}catch(t){this.store.showToast(G(t,"Could not clear logs"),!0)}}};var Ad=3500,Li=class{host;ws;entity;groups;tools;sub;routingRt={routeApplying:!1,scrollGen:0,handoffArming:!1};currentScope="device";currentViewId="select_device_prompt";activeSubentryId="";deviceSelected=!1;deviceLoading=!1;state=null;loading=!0;loadError="";studioRevMismatch=!1;toastMessage="";toastIsError=!1;politeAnnouncement="";assertiveAnnouncement="";politeSeq=0;assertiveSeq=0;toastTimer=null;liveClockNowMs=Date.now();liveClockTimer=null;selectedBackupFile=null;deviceSortField="title";deviceSortAsc=!0;deviceCategoryFilter="all";discoveredBleSearch="";discoveredBleKindFilter="all";discoveredBleSort="name";discoveredBlePaused=!1;discoveredBleFrozenSnapshot=null;discoveredIgnoredOpen=!1;discoveredBlePersonDrafts=new Map;discoveredLatterGroupDrafts=new Map;discoveredLatterPersonDrafts=new Map;discoveredBleSeenCache=new Map;devicePinDraft="";systemPinDraft="";pinBusy=!1;worldClockNewLabel="";worldClockNewZone="";worldClockRowKeys=[];worldClockRowSeq=0;overviewAlarmsOpen=!1;activeCameraPreviewEntity="";cameraPreviewUrl="";photosFilterCollection=de;photosSearch="";photosPage=1;photosSelectMode=!1;photosSelectedIds=new Set;photosNewCollectionOpen=!1;photosNewCollectionName="";photosRenamingCollectionId="";photosRenamingCollectionName="";photosBulkTargetCollectionId="";newGroupFormOpen=!1;newGroupName="";newGroupDesc="";newGroupSourceSubentryId="";newGroupIncludeDisplay=!1;newGroupIncludeInterface=!1;openGroupIds=new Set;groupCopySourceDrafts=new Map;batchTargetFilter="all";batchCategoryFilter="all";batchCopySourceSubentryId="";openBatchCategories=new Set;batchDraft=new Map;bleSurveySubentryId="";bleCalibrateAreaId="";bleCalibrateHandoffActive=!1;bleLiveStreamActive=!0;bleSurveyFrozen=new Map;openProxyTrims=new Set;advancedBleOpen=!1;openFusionAreas=new Set;announceMode="notify";announceTarget="all";announceTitle="";announceMessage="";announcePriority="normal";announceIncludeCamera=!1;doorbellTestSubentryId="";doorbellTestReply="";backupExportScope="system";backupRestoreSubentryId="";logsOpen=!1;logFilter="all";confirmModal=Bo();removeModal={open:!1,subentryId:"",title:"",busy:!1};resetModal={open:!1,deviceSettings:!0,latterOptions:!0,busy:!1};addBleModal={open:!1,candidateAddr:"",name:"",address:"",assignedPerson:"",bleCategory:"auto",busy:!1};colorWheelModal={open:!1,targetScope:"system",hex:"",name:"",busy:!1,painted:!1};saveGroupModal={open:!1,subentryId:"",name:"",description:"",includeDisplay:!1,includeInterface:!1,busy:!1};shortcutModal={open:!1,listKey:"pinned_items",editIndex:null,kind:"route",routeTarget:"weather:moon",entityDomainFilter:"all",entitySearch:"",entityTarget:"",action:"",label:"",icon:"",iconSearch:"",iconStyleFilter:"all",badgeStyle:"",accent:"",confirm:!1};appConfigModal={open:!1,app:null};cameraConfigModal={open:!1,cameraId:"",label:"",showListen:!1,showTalk:!1,showReply:!1,unlockEntity:""};photoUploadModal=Jt();photoEditModal=Qt();mediaImportModal=eo();photoPickerModal=Mt();returnToPinnedModal=!1;pendingScrollCardId="";handoffTargetIds=new Set;pendingDomRevert=null;pendingSystemPatch={};pendingSystemPrevious={};systemSaveTimer=null;pendingBlankListSlots={calendar_entities:0,camera_entities:0,remotes_list:0,thermostat_entities:0,lock_entities:0,garage_entities:0,vacuum_entities:0,broadcast_speakers:0,broadcast_phrases:0};pendingDeviceBuckets=new Map;pendingEntityStates=new Map;deviceConfigRevs=new Map;constructor(t){this.host=t,this.ws=new yi(()=>{this.handleStudioRevMismatch()}),this.entity=new Ii(this),this.groups=new Mi(this),this.tools=new Ri(this),this.sub=new Di(this)}get localeOverlay(){let t=this.state?.locale_strings;return t&&typeof t=="object"?t:null}t(t,o){return B(t,o,this.localeOverlay)}tPrefLabel(t,o){return Co(t,o,this.localeOverlay)}tPrefOption(t,o){return To(t,o,this.localeOverlay)}openConfirm(t){this.tools.openConfirm(t)}closeConfirm(){this.tools.closeConfirm()}async runConfirmedAction(){await this.tools.runConfirmedAction()}getKnownDeviceConfigRev(t){return this.state?.subentry_id===t&&this.state.device_config_rev>0?this.state.device_config_rev:this.deviceConfigRevs.get(t)??0}recordKnownDeviceConfigRev(t,o){t&&o>0&&this.deviceConfigRevs.set(t,o)}activeTimerRemainingSec(){let t=this.state?.live;if(!t)return 0;if(t.timer_running&&t.timer_ends_at){let o=Date.parse(t.timer_ends_at);if(Number.isFinite(o))return Math.max(0,Math.ceil((o-this.liveClockNowMs)/1e3))}return Math.max(0,Math.round(Number(t.timer_remaining_sec||0)))}activeStopwatchElapsedSec(){let t=this.state?.live;if(!t)return 0;if(t.stopwatch_running&&t.stopwatch_started_at){let o=Date.parse(t.stopwatch_started_at);if(Number.isFinite(o))return Math.max(0,Math.floor((this.liveClockNowMs-o)/1e3))}return Math.max(0,Math.round(Number(t.stopwatch_elapsed_sec||0)))}syncLiveClockTimer(){let t=this.state?.live;this.host.isConnected&&this.currentScope==="device"&&this.deviceSelected&&!this.deviceLoading&&this.currentViewId==="dashboard"&&!!(t?.timer_running&&t.timer_ends_at||t?.stopwatch_running&&t.stopwatch_started_at)?(this.liveClockNowMs=Date.now(),this.liveClockTimer===null&&(this.liveClockTimer=setInterval(()=>{this.liveClockNowMs=Date.now(),this.host.requestUpdate()},1e3))):this.liveClockTimer!==null&&(clearInterval(this.liveClockTimer),this.liveClockTimer=null)}hostConnected(){this.sub.syncConnectionListener(),this.syncLiveClockTimer(),this.ws.hass&&!this.studioRevMismatch&&this.ensureSubscription(!1)}hostDisconnected(){this.toastTimer&&(clearTimeout(this.toastTimer),this.toastTimer=null),this.sub.clearReconnectTimer(),this.liveClockTimer!==null&&(clearInterval(this.liveClockTimer),this.liveClockTimer=null),this.sub.detachConnectionListener(),this.entity.flushAllPendingSettings(),this.teardownSubscription()}hostUpdated(){Hr(this,this.routingRt)}mergeDomRevert(t){this.pendingDomRevert={controlIds:{...this.pendingDomRevert?.controlIds||{},...t}}}isHandoffTarget(t){return!!t&&this.handoffTargetIds.has(t)}clearHandoffTargets(){this.bleCalibrateHandoffActive=!1,this.handoffTargetIds.clear(),this.routingRt.handoffArming=!1}applySectionHandoff(t="",o){Ur(this,this.routingRt,t,o)}onMainFocusIn(t){Fr(this,this.routingRt,t)}handleStudioRevMismatch(){this.studioRevMismatch=!0,this.loading=!1,this.deviceLoading=!1,this.sub.clearReconnectTimer(),this.teardownSubscription(),this.host.requestUpdate()}setHass(t){let o=this.ws.hass?.connection??null;this.ws.setHass(t),this.sub.syncConnectionListener(),t?.connection&&t.connection!==o&&this.host.isConnected&&!this.studioRevMismatch&&this.ensureSubscription(!1)}get hass(){return this.ws.hass}reloadPage(){globalThis.location.reload()}announcePolite(t){let o=String(t||"").trim();o&&(this.politeSeq+=1,this.politeAnnouncement=this.politeSeq%2===0?`${o}\u200B`:o,this.host.requestUpdate())}announceAssertive(t){let o=String(t||"").trim();o&&(this.assertiveSeq+=1,this.assertiveAnnouncement=this.assertiveSeq%2===0?`${o}\u200B`:o,this.host.requestUpdate())}showToast(t,o=!1){let i=String(t||"");this.toastMessage=i,this.toastIsError=o,this.toastTimer&&(clearTimeout(this.toastTimer),this.toastTimer=null),o?this.announceAssertive(i):(this.announcePolite(i),this.toastTimer=setTimeout(()=>{this.toastMessage="",this.host.requestUpdate()},Ad)),this.host.requestUpdate()}dismissToast(){this.toastTimer&&(clearTimeout(this.toastTimer),this.toastTimer=null),this.toastMessage="",this.toastIsError=!1,this.host.requestUpdate()}shouldIncludeLogs(){return this.currentScope==="system"&&this.currentViewId==="system_tools"&&this.logsOpen}get pageTitle(){let t=rs[this.currentViewId]||"view.select_device_prompt";return this.t(t)}get pageSubtitle(){return this.currentScope==="device"&&this.deviceSelected&&this.currentViewId!=="select_device_prompt"&&this.currentViewId!=="discovered_devices"?this.state?.subentry_id===this.activeSubentryId&&this.state.title?this.state.title:this.state?.system_devices?.find(o=>o.subentry_id===this.activeSubentryId)?.title||"":""}get hasConfiguredSecurityPin(){return!!(this.state?.config?.has_security_pin??this.state?.live?.has_security_pin??this.state?.has_security_pin)}deviceHasView(t){return Nr(this,t)}onActiveDeviceChanged(t,o,i){Vr(this,t,o,i)}applyRoute(t){qr(this,this.routingRt,t)}redirectInvalidDeviceRoute(t){Gr(this,t)}syncUrl(t=!1){zr(this,this.routingRt,t)}openDevicesLanding(){Kr(this)}openDiscoveredDevices(t=""){Wr(this,t)}openDevicesWithCategory(t){this.deviceCategoryFilter=t,this.openDevicesLanding()}setScope(t,o){jr(this,t,o)}switchView(t){Yr(this,t)}openSystemSection(t,o="",i){this.switchView(t),this.applySectionHandoff(o,i)}openDeviceSection(t,o="",i){this.switchView(t),this.applySectionHandoff(o,i)}openManageGroups(t=""){let o=String(t||"").trim();if(o&&o!=="custom"){this.openGroupIds.add(o),this.openSystemSection("system_sync",`group-box-${o}`);return}this.openSystemSection("system_sync")}async switchSystemDevice(t,o="dashboard"){await Zr(this,t,o)}openHaPage(t){_t(t,!1)}openDeviceInHa(t=!1){Xr(this,t)}toggleParentHaSidebar(){this.host.dispatchEvent(new CustomEvent("hass-toggle-menu",{bubbles:!0,composed:!0}))}teardownSubscription(){this.sub.teardownSubscription()}desiredSubscriptionKey(){return this.sub.desiredSubscriptionKey()}async ensureSubscription(t=!1){await this.sub.ensureSubscription(t)}async refreshState(t){await this.sub.refreshState(t)}applyBleSurveyDelta(t){this.sub.applyBleSurveyDelta(t)}ingestPayload(t,o){this.sub.ingestPayload(t,o)}toggleDiscoveredBlePause(t){this.sub.toggleDiscoveredBlePause(t)}evictAdoptedBleCandidate(t){this.sub.evictAdoptedBleCandidate(t)}ensureDefaultSurveyDevice(){this.sub.ensureDefaultSurveyDevice()}ensureDefaultDoorbellTester(){this.sub.ensureDefaultDoorbellTester()}ensureValidBatchTargetFilter(){this.sub.ensureValidBatchTargetFilter()}};var Ed=new Set(["UTC","Etc/UTC","GMT","Etc/GMT","Etc/GMT+0","Etc/GMT-0","Etc/GMT0"]),Id=/^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;function Oi(e){let t=String(e||"").trim();return!!(t&&!Ed.has(t)&&Id.test(t))}function Re(e,t=32,o=!0){let i=String(e??""),a="",n=o;for(let c of i){let u=c.charCodeAt(0);if(u<32||u===127||c==="|"||c===";"||c===""||c===""||c===" "||c==="	"||c==="\r"||c===`
`){n||(a+=" ",n=!0);continue}a+=c,n=!1}let s=o?a.trim():a,r=vs(s,t);return o?r.trimEnd():r}function Pd(e){let t=e.split("/").pop()||e;return Re(t.replace(/_/g," "))||e}function Qr(e){let t=[],o=new Set;for(let i of String(e??"").split(";")){let a=i.trim();if(!a)continue;let n=a.indexOf("|");if(n<0)continue;let s=a.slice(0,n),r=a.slice(n+1).trim();if(!Oi(r))continue;let c=Re(s)||Pd(r),u=`${c.toLowerCase()}|${r}`;if(!o.has(u)&&(o.add(u),t.push({label:c,iana:r}),t.length>=ko))break}return t}function el(e){return e.slice(0,ko).map(t=>{let o=Re(t.label);return o?`${o}|${t.iana}`:""}).filter(Boolean).join(";")}var tl=600;function an(e){return e.key==="Enter"&&!e.isComposing&&e.keyCode!==229}function ol(e){let t=e.state,o=t?.config||{},i=t?.world_clock_zones?.length?t.world_clock_zones:ua,a=new Set(i.map($=>$.iana)),n=e.entity.getPref("local_clock_label"),s=Re(n?.value??o.local_clock_label??""),r=e.entity.getPref("show_utc_clock"),c=r?!!r.value:!!o.show_utc_clock,u=e.entity.getPref("world_clocks"),p=Qr(u?.value??o.world_clocks??""),d=p.length>=ko;for(;e.worldClockRowKeys.length<p.length;)e.worldClockRowSeq+=1,e.worldClockRowKeys.push(`wc-${e.worldClockRowSeq}`);e.worldClockRowKeys.length>p.length&&(e.worldClockRowKeys.length=p.length);let m=$=>{let P=$&&!a.has($)?l`<option value=${$} .selected=${S(!0)}>${$}</option>`:v;return l`${P}${i.map(H=>l`<option value=${H.iana} .selected=${S(H.iana===$)}>${H.label}</option>`)}`},g=($,P,H)=>{e.entity.stageDeviceSetting("world_clocks",el($),P,H)},_=($,P,H,C,L=!0)=>{if($<0||$>=p.length)return;let D=p[$];if(!D)return;let z=(P.iana??D.iana).trim();if(!Oi(z))return;let Z=P.label!==void 0?Re(P.label,32,L):D.label;if(!Z.trim()||p.some((ee,oe)=>oe!==$&&ee.iana===z&&ee.label.toLowerCase()===Z.trim().toLowerCase()))return;let Q=p.map((ee,oe)=>oe===$?{label:Z.trim(),iana:z}:{...ee});g(Q,H,C)},h=($,P)=>{if($<0||P<0||$>=p.length||P>=p.length||$===P)return;let H=[...p],[C]=H.splice($,1);if(C){if(H.splice(P,0,C),e.worldClockRowKeys.length===p.length){let[L]=e.worldClockRowKeys.splice($,1);L!==void 0&&e.worldClockRowKeys.splice(P,0,L)}g(H)}},b=$=>{$>=0&&$<e.worldClockRowKeys.length&&e.worldClockRowKeys.splice($,1),g(p.filter((P,H)=>H!==$))},y=()=>e.host?.renderRoot??null,f=()=>{if(d)return;let $=y(),P=$?.getElementById("cfg-world_clock_new_label"),H=$?.getElementById("cfg-world_clocks_add"),C=Re(P?.value??e.worldClockNewLabel),L=(H?.value??e.worldClockNewZone).trim();if(!C){e.showToast(e.t("dialogs.toast_enter_city"),!0),P?.focus();return}if(!Oi(L)){e.showToast(e.t("dialogs.toast_select_tz"),!0),H?.focus();return}if(p.some(z=>z.iana===L&&z.label.toLowerCase()===C.toLowerCase())){e.showToast(e.t("dialogs.toast_dup_world_clock"),!0);return}e.worldClockNewLabel="",e.worldClockNewZone="",P&&(P.value=""),H&&(H.value=""),e.worldClockRowSeq+=1,e.worldClockRowKeys.push(`wc-${e.worldClockRowSeq}`),g([...p,{label:C,iana:L}],"btn-world_clock_add")},k=e.entity.getPref("time_format"),w=e.entity.getPrefSpec("time_format"),M=k?.options&&k.options.length>0?k.options:w?.options||[],E=k?.value??o.time_format,N=E!=null&&String(E).trim()!==""?String(E):$e(e.hass);return l`<div class="settings-list">
    ${M.length>0?se({id:"cfg-time_format",label:e.tPrefLabel("time_format"),description:e.t("dev_interface.time_format_desc"),value:M.includes(N)?N:M[0],rawOptions:M.map($=>({value:$,label:e.tPrefOption("time_format",$)})),onChange:$=>e.entity.stageDeviceSetting("time_format",$,"cfg-time_format")}):v}
    ${R({id:"time-local-clock-label",label:e.t("dialogs.local_clock_label"),forId:"cfg-local_clock_label",description:e.t("dialogs.local_clock_desc"),control:l`<input
        type="text"
        id="cfg-local_clock_label"
        maxlength="32"
        enterkeyhint="done"
        placeholder=${e.t("dialogs.optional_label_placeholder")}
        .value=${V(s)}
        @input=${$=>{let P=Re($.currentTarget.value,32,!1);e.entity.stageDeviceSetting("local_clock_label",P,"cfg-local_clock_label",tl)}}
        @change=${$=>{let P=$.currentTarget,H=Re(P.value);P.value=H,e.entity.stageDeviceSetting("local_clock_label",H,"cfg-local_clock_label")}}
        @keydown=${$=>{if(!an($))return;$.preventDefault();let P=$.currentTarget,H=Re(P.value);P.value=H,e.entity.stageDeviceSetting("local_clock_label",H,"cfg-local_clock_label"),e.entity.flushAllPendingSettings()}}
      />`})}
    ${j({id:"cfg-show_utc_clock",label:e.t("dialogs.show_utc_label"),description:e.t("dialogs.show_utc_desc"),checked:c,onChange:$=>{e.entity.stageDeviceSetting("show_utc_clock",$,"cfg-show_utc_clock")}})}
    ${R({id:"time-world-clocks",label:e.t("dialogs.world_clocks_label"),description:e.t("dialogs.world_clocks_desc"),stacked:!0,control:l`<div class="stack">
        ${p.length>0?Fe({id:"world-clocks-list",ariaLabel:e.t("dialogs.world_clocks_aria"),items:p,getKey:($,P)=>e.worldClockRowKeys[P]||`wc-row-${P}`,getLabel:$=>$.label,onReorder:h,overlay:e.localeOverlay,renderContent:($,P)=>{let H=`cfg-world_clock_${P+1}_label`,C=`cfg-world_clock_${P+1}_zone`;return l`<div class="list-row-main">
                  <div class="stacked-field">
                    <label for=${H}>
                      ${e.t("dialogs.world_clock_city_label",{index:P+1})}
                    </label>
                    <input
                      type="text"
                      id=${H}
                      maxlength="32"
                      enterkeyhint="done"
                      placeholder=${e.t("dialogs.city_label_placeholder")}
                      .value=${V($.label)}
                      @input=${L=>{let D=Re(L.currentTarget.value,32,!1);D.trim()&&_(P,{label:D},H,tl,!1)}}
                      @change=${L=>{let D=L.currentTarget,z=Re(D.value);if(!z){D.value=$.label,e.showToast(e.t("dialogs.toast_city_empty"),!0);return}D.value=z,_(P,{label:z},H)}}
                      @keydown=${L=>{if(!an(L))return;L.preventDefault();let D=L.currentTarget,z=Re(D.value);if(!z){D.value=$.label,e.showToast(e.t("dialogs.toast_city_empty"),!0);return}D.value=z,_(P,{label:z},H),e.entity.flushAllPendingSettings()}}
                    />
                  </div>
                  <div class="stacked-field">
                    <label for=${C}>
                      ${e.t("dialogs.world_clock_zone_label",{index:P+1})}
                    </label>
                    <select
                      id=${C}
                      .value=${S($.iana)}
                      @change=${L=>_(P,{iana:L.currentTarget.value},C)}
                    >
                      ${m($.iana)}
                    </select>
                  </div>
                </div>`},renderActions:($,P)=>Se(e.t("action.remove_item",{item:`${$.label} (${$.iana})`}),()=>b(P))}):v}
        <div class="list-row">
          <div class="list-row-main">
            <div class="stacked-field">
              <label for="cfg-world_clock_new_label">
                ${e.t("dialogs.new_city_label")}
              </label>
              <input
                type="text"
                id="cfg-world_clock_new_label"
                maxlength="32"
                enterkeyhint="done"
                placeholder=${e.t("dialogs.city_label_placeholder")}
                ?disabled=${d}
                .value=${V(e.worldClockNewLabel)}
                @input=${$=>{e.worldClockNewLabel=$.currentTarget.value,e.host.requestUpdate()}}
                @keydown=${$=>{an($)&&($.preventDefault(),f())}}
              />
            </div>
            <div class="stacked-field">
              <label for="cfg-world_clocks_add">${e.t("dialogs.add_time_zone")}</label>
              <select
                id="cfg-world_clocks_add"
                ?disabled=${d}
                .value=${S(e.worldClockNewZone)}
                @change=${$=>{e.worldClockNewZone=$.currentTarget.value,e.host.requestUpdate()}}
              >
                <option value="" .selected=${S(!e.worldClockNewZone)}>
                  ${d?e.t("dialogs.max_world_clocks"):e.t("dialogs.select_tz_placeholder")}
                </option>
                ${d?v:m(e.worldClockNewZone)}
              </select>
            </div>
          </div>
          <button
            type="button"
            id="btn-world_clock_add"
            ?disabled=${d}
            @click=${()=>f()}
            class="btn btn-primary"
          >
            ${e.t("action.add")}
          </button>
        </div>
      </div>`})}
  </div>`}var Md={pinned:"dialogs.app_pinned",home_hub:"dialogs.app_home_hub",cameras:"dialogs.app_cameras",area:"dialogs.app_area",music:"dialogs.app_music",remote:"dialogs.app_remote",weather:"dialogs.app_weather",time:"dialogs.app_time",calendar:"dialogs.app_calendar",clock:"dialogs.app_clock",tools:"dialogs.app_tools",games:"dialogs.app_games"};function Bi(e,t,o){let i=e.filter(r=>me(r,o)),a=new Map(i.map(r=>[r.token,r])),n=new Set,s=[];for(let r of t){let c=a.get(r);!c||n.has(r)||(n.add(r),s.push({token:r,label:c.label,enabled:!0}))}for(let r of i)n.has(r.token)||s.push({token:r.token,label:r.label,enabled:!1});return s}function il(e,t,o){let i=e.entity.getPref(t),a=e.entity.getPrefSpec(t),n=i?.options&&i.options.length>0?i.options:a?.options||[];return t==="clock_face"&&o?.is_round===!1?n.filter(s=>s!=="Modern Analog"):n}function al(e,t,o){let i=e.entity.getPref(t),a=e.state?.config?.[t],n=e.entity.getPrefSpec(t),s=i?.value??a,r=t==="time_format"?$e(e.hass):n?.default??"",c=s!=null&&String(s).trim()!==""?String(s):String(r);return o.length>0&&!o.includes(c)?o[0]??c:c}function bt(e,t,o,i,a){let n=il(e,t,i);if(n.length===0)return v;let s=al(e,t,n);return se({id:o||void 0,label:e.tPrefLabel(t),description:a,value:s,rawOptions:n.map(r=>({value:r,label:e.tPrefOption(t,r)})),onChange:r=>e.entity.stageDeviceSetting(t,r,o||void 0)})}function nl(e){let t=e.appConfigModal.app;if(!t)return v;let o=e.state,i=o?.config||{},a=o?.capabilities,n=Md[t],s=n?e.t(n):e.t("dialogs.app_fallback"),r,c=v,u=!0;if(t==="pinned"){u=!1;let p=e.entity.getPinnedItems(),d=new Map((o?.catalog?.shortcut_entities||[]).map(_=>[_.id,_])),m=new Map(Be.map(_=>[_.token,_])),g=_=>{if(_.kind==="route"){let k=m.get(_.target);return{displayTitle:_.label||k?.label||_.target,metaLine:k?`${k.group} \u2022 ${k.label}`:_.target,iconSlug:_.icon||nt[_.target]||"mdi:apps"}}let h=d.get(_.target),b=_.target.split(".",1)[0]||"",y=bi(b,_.action),f=_.confirm?e.t("dialogs.pinned_confirm_mode"):e.t("dialogs.pinned_one_tap_mode");return{displayTitle:_.label||h?.name||_.target,metaLine:`${y} \u2022 ${f} \u2022 ${_.target}`,iconSlug:_.icon||h?.icon||"mdi:flash"}};r=l`<div class="settings-list">
      ${R({id:"pinned-shortcuts-row",label:e.t("dialogs.pinned_label"),description:e.t("dialogs.pinned_desc"),stacked:!0,control:l`<div class="stack">
          ${Fe({id:"pinned-shortcuts-container",ariaLabel:e.t("dialogs.pinned_aria"),items:p,rowClass:"shortcut-item-row",emptyState:e.t("dialogs.pinned_empty"),overlay:e.localeOverlay,getKey:_=>`${_.kind}|${_.target}|${_.action}`,getLabel:_=>g(_).displayTitle,onReorder:(_,h)=>e.entity.reorderShortcutItems("pinned_items",_,h),renderContent:(_,h)=>{let b=g(_),y=Math.floor(h/6)+1;return l`<div class="shortcut-icon-row">
                <span class=${Bt(_.badge_style,_.accent)} aria-hidden="true">
                  <ha-icon .icon=${b.iconSlug}></ha-icon>
                </span>
                <div class="shortcut-item-info">
                  <span class="shortcut-item-title">${b.displayTitle}</span>
                  <span class="shortcut-item-meta">${b.metaLine}</span>
                </div>
                <span class="chip">
                  ${e.t("dialogs.pinned_page_slot",{page:y})}
                </span>
              </div>`},renderActions:(_,h)=>{let b=g(_);return l`<button
                  type="button"
                  aria-label=${e.t("action.edit_item",{item:b.displayTitle})}
                  @click=${()=>e.entity.openShortcutModal("pinned_items",h)}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("action.edit")}
                </button>
                ${Se(e.t("action.remove_item",{item:b.displayTitle}),()=>e.entity.removeShortcutItem("pinned_items",h))}`}})}
          <div class="shortcut-toolbar">
            <button
              type="button"
              id="btn-add-pinned-item"
              ?disabled=${p.length>=yo}
              @click=${()=>e.entity.openShortcutModal("pinned_items",null)}
              class="btn btn-primary"
            >
              ${e.t("action.add_pinned_item")}
            </button>
          </div>
        </div>`})}
    </div>`}else if(t==="home_hub"){let p=e.entity.getEnabledHomeCategories(),d=Bi(Et,p,a),m=e.entity.getSystemBroadcastSpeakers(),g=e.entity.getBroadcastSpeakers(),_=new Map((o?.catalog?.ma_speakers||[]).map(f=>[f.id,f])),h=f=>{let k=_.get(f);if(!k?.name)return f;let w=k.name.replace(/\s*\([^)]*\)\s*(?:\(unavailable\))?$/,"").trim();return w?te(w):f},b=new Set(g),y=[...g.map(f=>({token:f,label:h(f),enabled:!0})),...m.filter(f=>!b.has(f)).map(f=>({token:f,label:h(f),enabled:!1}))];r=l`<div class="settings-list">
      ${R({label:e.t("dialogs.home_cats_label"),description:e.t("dialogs.home_cats_desc"),stacked:!0,control:Ve({id:"home-categories-pills",ariaLabel:e.t("dialogs.home_cats_label"),items:d,onToggle:(f,k)=>e.entity.toggleHomeCategoryToken(f,k),onReorder:(f,k)=>e.entity.reorderHomeCategories(f,k),overlay:e.localeOverlay})})}
      ${R({id:"home-broadcast-speakers-row",label:e.t("dialogs.broadcast_speakers_label"),description:e.t("dialogs.broadcast_speakers_desc"),stacked:!0,control:m.length>0?Ve({id:"broadcast-speakers-pills",ariaLabel:e.t("dialogs.broadcast_speakers_label"),items:y,onToggle:(f,k)=>e.entity.toggleBroadcastSpeaker(f,k),onReorder:(f,k)=>e.entity.reorderBroadcastSpeakers(f,k),overlay:e.localeOverlay}):l`<p class="empty-state">
                ${e.t("dialogs.broadcast_speakers_empty_system")}
              </p>`})}
    </div>`,c=l`<button
      type="button"
      @click=${()=>{e.entity.closeAppConfigModal(),e.openSystemSection("shared_entities","card-whole-home")}}
      class="btn btn-text"
    >
      ${e.t("action.open_shared_entities")}
    </button>`}else if(t==="cameras"){let p=e.entity.getSystemCameraEntities(),d=e.entity.getVisibleCameras(),m=e.entity.getCarouselCameras(),g=new Map((o?.catalog?.cameras||[]).map(w=>[w.id,w])),_=o?.system_config?.camera_configs||{},h=w=>{let M=String(_[w]?.label||"").trim();if(M)return M;let E=g.get(w);return E?.name?te(E.name):w},b=new Set(d),y=[...d.map(w=>({token:w,label:h(w),enabled:!0})),...p.filter(w=>!b.has(w)).map(w=>({token:w,label:h(w),enabled:!1}))],f=new Set(m),k=[...m.map(w=>({token:w,label:h(w),enabled:!0})),...d.filter(w=>!f.has(w)).map(w=>({token:w,label:h(w),enabled:!1}))];r=l`<div class="settings-list">
      ${bt(e,"camera_default_view","cfg-camera_default_view",a,e.t("dialogs.camera_default_view_desc"))}
      ${bt(e,"camera_framing","cfg-camera_framing",a,e.t("dialogs.camera_framing_desc"))}
      ${bt(e,"camera_carousel_interval","cfg-camera_carousel_interval",a,e.t("dialogs.camera_carousel_interval_desc"))}
      ${bt(e,"camera_stream_mode","cfg-camera_stream_mode",a,e.t("dialogs.camera_stream_mode_desc"))}
      ${a?.hw_jpeg===!0?bt(e,"camera_doorbell_popup","cfg-camera_doorbell_popup",a,e.t("dialogs.camera_doorbell_popup_desc")):v}
      ${R({id:"camera-visible-row",label:e.t("dialogs.camera_visible_label"),description:e.t("dialogs.camera_visible_desc"),stacked:!0,control:p.length>0?Ve({id:"camera-visible-pills",ariaLabel:e.t("dialogs.camera_visible_label"),items:y,onToggle:(w,M)=>e.entity.toggleVisibleCamera(w,M),onReorder:(w,M)=>e.entity.reorderVisibleCameras(w,M),overlay:e.localeOverlay}):l`<p class="empty-state">${e.t("dialogs.cameras_empty_system")}</p>`})}
      ${p.length>0?R({id:"camera-carousel-row",label:e.t("dialogs.camera_carousel_label"),description:e.t("dialogs.camera_carousel_desc"),stacked:!0,control:Ve({id:"camera-carousel-pills",ariaLabel:e.t("dialogs.camera_carousel_label"),items:k,onToggle:(w,M)=>e.entity.toggleCarouselCamera(w,M),onReorder:(w,M)=>e.entity.reorderCarouselCameras(w,M),overlay:e.localeOverlay})}):v}
    </div>`,c=l`<button
      type="button"
      id="btn-cameras-open-shared"
      @click=${()=>{e.entity.closeAppConfigModal(),e.openSystemSection("shared_entities","card-cameras-doorbell")}}
      class="btn btn-text"
    >
      ${e.t("action.open_shared_entities")}
    </button>`}else if(t==="area"){let p=e.entity.getEnabledAreaCategories(),d=Bi(At,p,a);r=l`<div class="settings-list">
      ${R({label:e.t("dialogs.area_cats_label"),description:e.t("dialogs.area_cats_desc"),stacked:!0,control:Ve({id:"area-categories-pills",ariaLabel:e.t("dialogs.area_cats_label"),items:d,onToggle:(m,g)=>e.entity.toggleAreaCategoryToken(m,g),onReorder:(m,g)=>e.entity.reorderAreaCategories(m,g),overlay:e.localeOverlay})})}
    </div>`}else if(t==="music")r=l`<div class="settings-list">
      ${["album_art_style","music_overlay_style","music_auto_open","album_sort_order","artist_album_sort_order","podcast_sort_order"].map(d=>bt(e,d,`cfg-${d}`,a,d==="music_auto_open"?e.t("dialogs.music_auto_open_desc"):void 0))}
    </div>`;else if(t==="remote"){let p=o?.system_config?.remote_groups||[],d=(o?.system_devices||[]).find(_=>_.subentry_id===e.activeSubentryId),m=String(i.device_remote_group||d?.device_remote_group||"area_auto").trim()||"area_auto",g=[{value:"area_auto",label:e.t("dialogs.remote_follow_area")},...p.map(_=>({value:`group:${_.id}`,label:e.t("dialogs.remote_group_option",{name:_.name})})),{value:"all",label:e.t("dialogs.remote_all_system")}];if(!g.some(_=>_.value===m)){let _=m.startsWith("group:")?m.slice(6):m;g.push({value:m,label:e.t("dialogs.remote_missing_group",{id:_})})}r=l`<div class="settings-list">
      ${se({id:"cfg-device_remote_group",label:e.t("dialogs.remote_group_label"),description:e.t("dialogs.remote_group_desc"),value:m,rawOptions:g,onChange:_=>e.entity.stageDeviceSetting("device_remote_group",_,"cfg-device_remote_group")})}
    </div>`,c=l`<button
      type="button"
      @click=${()=>{e.entity.closeAppConfigModal(),e.openSystemSection("remotes","card-remote-groups")}}
      class="btn btn-text"
    >
      ${e.t("dialogs.manage_remote_groups")}
    </button>`}else if(t==="weather"){let d=e.entity.getPref("weather_app_background")?.value??i.weather_app_background,m=d!=null?typeof d=="string"?!["","0","false","off","disabled"].includes(d.trim().toLowerCase()):!!d:!0;r=l`<div class="settings-list">
      ${j({id:"cfg-weather_app_background",label:e.t("dialogs.weather_bg_label"),description:e.t("dialogs.weather_bg_desc"),checked:m,onChange:g=>e.entity.stageDeviceSetting("weather_app_background",g,"cfg-weather_app_background")})}
    </div>`,c=l`<button
      type="button"
      id="btn-weather-open-shared"
      @click=${()=>{e.entity.closeAppConfigModal(),e.openSystemSection("shared_entities","card-whole-home")}}
      class="btn btn-text"
    >
      ${e.t("action.open_shared_entities")}
    </button>`}else if(t==="time")u=!1,r=ol(e);else if(t==="clock")r=l`<div class="settings-list">
      ${bt(e,"clock_face","cfg-clock_face",a)}
      ${bt(e,"time_format","cfg-time_format",a)}
    </div>`;else if(t==="calendar"){let p=e.entity.getPref("calendar_lookahead_days"),d=Number(p?.value??i.calendar_lookahead_days??30),m=d<=10?7:d<=21?14:d<=45?30:60,g=il(e,"calendar_week_start",a),_=g.length>0?g:Qn,h=al(e,"calendar_week_start",_);r=l`<div class="settings-list">
      ${se({id:"cfg-calendar_lookahead_days",label:e.t("dialogs.calendar_lookahead_label"),description:e.t("dialogs.calendar_lookahead_desc"),value:String(m),rawOptions:ni.map(b=>({value:String(b.value),label:b.label})),onChange:b=>e.entity.stageDeviceSetting("calendar_lookahead_days",Number(b),"cfg-calendar_lookahead_days")})}
      ${se({id:"cfg-calendar_week_start",label:e.t("dialogs.calendar_week_start_label"),description:e.t("dialogs.calendar_week_start_desc"),value:h,rawOptions:_.map(b=>({value:b,label:e.tPrefOption("calendar_week_start",b)})),onChange:b=>e.entity.stageDeviceSetting("calendar_week_start",b,"cfg-calendar_week_start")})}
    </div>`,c=l`<button
      type="button"
      @click=${()=>{e.entity.closeAppConfigModal(),e.openSystemSection("shared_entities","card-calendars")}}
      class="btn btn-text"
    >
      ${e.t("action.open_shared_entities")}
    </button>`}else if(t==="tools"){let p=e.entity.getEnabledToolsItems(),d=Bi(it,p,a);r=l`<div class="settings-list">
      ${R({label:e.t("dialogs.tools_label"),description:e.t("dialogs.tools_desc"),stacked:!0,control:Ve({id:"tools-items-pills",ariaLabel:e.t("dialogs.tools_label"),items:d,onToggle:(m,g)=>e.entity.toggleToolItemToken(m,g),onReorder:(m,g)=>e.entity.reorderToolsItems(m,g),overlay:e.localeOverlay})})}
    </div>`}else{let p=e.entity.getEnabledGamesItems(),d=Bi(It,p,a);r=l`<div class="settings-list">
      ${R({label:e.t("dialogs.games_label"),description:e.t("dialogs.games_desc"),stacked:!0,control:Ve({id:"games-items-pills",ariaLabel:e.t("dialogs.games_label"),items:d,onToggle:(m,g)=>e.entity.toggleGameItemToken(m,g),onReorder:(m,g)=>e.entity.reorderGamesItems(m,g),overlay:e.localeOverlay})})}
    </div>`}return l`<div class="dialog-body">
    <h3 id="latter-app-config-title" class="dialog-title">${s}</h3>
    ${r}
    <div class="dialog-actions">
      ${c}
      <button
        type="button"
        id="app-config-done-btn"
        @click=${()=>e.entity.closeAppConfigModal()}
        class="btn ${u?"btn-primary":"btn-secondary"}"
      >
        ${e.t("action.done")}
      </button>
    </div>
  </div>`}function sl(e){let t=()=>e.entity.closeAppConfigModal();return l`<dialog
    id="latter-app-config-modal"
    aria-labelledby="latter-app-config-title"
    @cancel=${t}
    @click=${i=>{i.target===i.currentTarget&&t()}}
    class="studio-dialog shortcut-dialog"
  >
    ${e.appConfigModal.open?nl(e):v}
  </dialog>`}function rl(e,t){e.target===e.currentTarget&&t()}function sn(e,t){let i=(e.state?.catalog?.cameras||[]).find(c=>c.id===t),a=(e.state?.system_config?.camera_configs||{})[t]||{},n=!!i?.is_doorbell,s=!!i?.has_audio,r=!!i?.has_talkback;return{label:String(a.label||"").trim(),showListen:typeof a.show_listen=="boolean"?a.show_listen:n&&s,showTalk:typeof a.show_talk=="boolean"?a.show_talk:n&&r,showReply:typeof a.show_reply=="boolean"?a.show_reply:n&&r,unlockEntity:String(a.unlock_entity||"").trim(),meta:i}}function ll(e,t){let o=String(t||"").trim();if(!o)return;let i=sn(e,o);e.cameraConfigModal={open:!0,cameraId:o,label:i.label,showListen:i.showListen,showTalk:i.showTalk,showReply:i.showReply,unlockEntity:i.unlockEntity},e.host.requestUpdate()}function nn(e){e.cameraConfigModal.open&&(e.cameraConfigModal={...e.cameraConfigModal,open:!1},e.host.requestUpdate())}function Dd(e){let t=e.cameraConfigModal,o=String(t.cameraId||"").trim();if(!o){nn(e);return}let i={...e.state?.system_config?.camera_configs||{}},a={show_listen:!!t.showListen,show_talk:!!t.showTalk,show_reply:!!t.showReply},n=String(t.label||"").replace(/[|\x1e\x1f\r\n]/g," ").trim().slice(0,32);n&&(a.label=n);let s=String(t.unlockEntity||"").trim();(s.startsWith("lock.")||s.startsWith("cover."))&&(a.unlock_entity=s),i[o]=a,e.entity.stageSystemSetting("camera_configs",i),nn(e)}function cl(e){let t=e.cameraConfigModal,o=()=>nn(e);if(!t.open||!t.cameraId)return l`<dialog
      id="latter-camera-config-modal"
      aria-labelledby="latter-cam-cfg-title"
      @cancel=${o}
      @click=${u=>rl(u,o)}
      class="studio-dialog"
    >
      ${v}
    </dialog>`;let i=e.state?.catalog||{},a=(i.cameras||[]).find(u=>u.id===t.cameraId),n=a?.name?te(a.name):t.cameraId,s=i.locks||[],r=i.garages||[],c=!t.unlockEntity||s.some(u=>u.id===t.unlockEntity)||r.some(u=>u.id===t.unlockEntity);return l`<dialog
    id="latter-camera-config-modal"
    aria-labelledby="latter-cam-cfg-title"
    @cancel=${o}
    @click=${u=>rl(u,o)}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-cam-cfg-title" class="dialog-title">
          ${e.t("shared.cam_cfg_title")}
        </h3>
      </div>
      <p class="dialog-text">${n} (${t.cameraId})</p>

      <div class="settings-list">
        ${R({label:e.t("shared.cam_cfg_label"),description:e.t("shared.cam_cfg_label_desc"),forId:"cam-cfg-label",control:l`<input
            id="cam-cfg-label"
            type="text"
            maxlength="32"
            placeholder=${n}
            .value=${V(t.label)}
            @input=${u=>{e.cameraConfigModal={...e.cameraConfigModal,label:u.currentTarget.value}}}
          />`})}

        ${j({id:"cam-cfg-listen",label:e.t("shared.cam_cfg_listen"),description:e.t("shared.cam_cfg_listen_desc"),checked:t.showListen,onChange:u=>{e.cameraConfigModal={...e.cameraConfigModal,showListen:u},e.host.requestUpdate()}})}

        ${j({id:"cam-cfg-talk",label:e.t("shared.cam_cfg_talk"),description:a?.has_talkback?e.t("shared.cam_cfg_talk_desc"):e.t("shared.cam_cfg_talk_no_speaker_desc"),checked:t.showTalk,onChange:u=>{e.cameraConfigModal={...e.cameraConfigModal,showTalk:u},e.host.requestUpdate()}})}

        ${j({id:"cam-cfg-reply",label:e.t("shared.cam_cfg_reply"),description:e.t("shared.cam_cfg_reply_desc"),checked:t.showReply,onChange:u=>{e.cameraConfigModal={...e.cameraConfigModal,showReply:u},e.host.requestUpdate()}})}

        ${R({label:e.t("shared.cam_cfg_unlock"),description:e.t("shared.cam_cfg_unlock_desc"),forId:"cam-cfg-unlock",control:l`<select
            id="cam-cfg-unlock"
            .value=${S(t.unlockEntity)}
            @change=${u=>{e.cameraConfigModal={...e.cameraConfigModal,unlockEntity:u.currentTarget.value},e.host.requestUpdate()}}
          >
            <option value="" .selected=${S(!t.unlockEntity)}>
              ${e.t("shared.cam_cfg_unlock_none")}
            </option>
            ${!c&&t.unlockEntity?l`<option value=${t.unlockEntity} .selected=${S(!0)}>${t.unlockEntity}</option>`:v}
            ${s.length?l`<optgroup label=${e.t("shared.door_locks")}>
                  ${s.map(u=>l`<option value=${u.id} .selected=${S(t.unlockEntity===u.id)}>
                      ${te(u.name)}
                    </option>`)}
                </optgroup>`:v}
            ${r.length?l`<optgroup label=${e.t("shared.garage_doors")}>
                  ${r.map(u=>l`<option value=${u.id} .selected=${S(t.unlockEntity===u.id)}>
                      ${te(u.name)}
                    </option>`)}
                </optgroup>`:v}
          </select>`})}
      </div>

      <div class="dialog-actions">
        <button type="button" @click=${o} class="btn btn-secondary">
          ${e.t("action.cancel")}
        </button>
        <button
          id="cam-cfg-save"
          type="button"
          @click=${()=>Dd(e)}
          class="btn btn-primary"
        >
          ${e.t("action.save")}
        </button>
      </div>
    </div>
  </dialog>`}function Rd(e){let t=e.getContext("2d");if(!t)return;let o=e.width,i=o/2,a=t.createImageData(o,o),n=a.data;for(let s=0;s<o;s+=1)for(let r=0;r<o;r+=1){let c=r-i,u=s-i,p=Math.sqrt(c*c+u*u),d=(s*o+r)*4;if(p>i){n[d+3]=0;continue}let m=Math.min(1,p/i),g=(Math.atan2(u,c)*180/Math.PI+360)%360,[_,h,b]=Ea(g,m,1);n[d]=_,n[d+1]=h,n[d+2]=b,n[d+3]=255}t.putImageData(a,0,0)}function dl(e,t){let o=e.getBoundingClientRect();if(!o.width||!o.height)return null;let i=o.width/2,a=o.height/2,n=t.clientX-o.left-i,s=t.clientY-o.top-a,r=Math.min(i,a),c=Math.min(1,Math.sqrt(n*n+s*s)/r),u=(Math.atan2(s,n)*180/Math.PI+360)%360;return hs(u,c,1)}function ul(e,t){if(t.colorWheelModal.open&&!t.colorWheelModal.painted){let o=e.getElementById("latter-cw-canvas");o&&(Rd(o),t.colorWheelModal.painted=!0)}else!t.colorWheelModal.open&&t.colorWheelModal.painted&&(t.colorWheelModal.painted=!1)}function pl(e){let t=e.colorWheelModal,o=p=>{p.target===p.currentTarget&&!t.busy&&e.tools.closeColorWheelModal()},i=p=>{t.busy?p.preventDefault():e.tools.closeColorWheelModal()};if(!t.open)return l`<dialog
      id="latter-cw-modal"
      aria-labelledby="latter-cw-title"
      @cancel=${i}
      @click=${o}
      class="studio-dialog"
    >
      ${v}
    </dialog>`;let a=p=>{let d=p,m=d.currentTarget;m.setPointerCapture?.(d.pointerId);let g=dl(m,d);g&&(e.colorWheelModal={...e.colorWheelModal,hex:g},e.host.requestUpdate())},n=p=>{let d=p;if(d.buttons===0)return;let m=d.currentTarget,g=dl(m,d);g&&(e.colorWheelModal={...e.colorWheelModal,hex:g},e.host.requestUpdate())},s=p=>{let d=p,m=d.currentTarget;m.hasPointerCapture?.(d.pointerId)&&m.releasePointerCapture(d.pointerId)},r=p=>{let d=p.currentTarget.value;e.colorWheelModal={...e.colorWheelModal,hex:d.toUpperCase()},e.host.requestUpdate()},c=p=>{e.colorWheelModal={...e.colorWheelModal,name:p.currentTarget.value}},u=ue(t.hex)?t.hex:"#3898FF";return l`<dialog
    id="latter-cw-modal"
    aria-labelledby="latter-cw-title"
    @cancel=${i}
    @click=${o}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-cw-title" class="dialog-title">${e.t("dialogs.cw_title")}</h3>
      <div class="color-wheel" aria-hidden="true">
        <canvas
          id="latter-cw-canvas"
          width="220"
          height="220"
          @pointerdown=${a}
          @pointermove=${n}
          @pointerup=${s}
        ></canvas>
      </div>
      <div class="color-hex-row">
        <input
          type="color"
          id="latter-cw-native"
          aria-label=${e.t("dialogs.cw_color_aria")}
          .value=${S(u)}
          @input=${r}
        />
        <input
          type="text"
          id="latter-cw-hex"
          aria-label=${e.t("dialogs.cw_hex_aria")}
          placeholder="#RRGGBB"
          maxlength="7"
          .value=${V(t.hex)}
          @input=${r}
        />
      </div>
      <div class="stacked-field">
        <label for="latter-cw-name">${e.t("dialogs.cw_name_label")}</label>
        <input
          type="text"
          id="latter-cw-name"
          placeholder=${e.t("dialogs.cw_name_placeholder")}
          .value=${V(t.name)}
          @input=${c}
        />
      </div>
      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${t.busy}
          @click=${()=>e.tools.closeColorWheelModal()}
          class="btn btn-secondary"
        >
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          ?disabled=${t.busy}
          @click=${()=>{e.tools.saveColorWheelSelection()}}
          class="btn btn-primary"
        >
          ${e.t("action.save_color")}
        </button>
      </div>
    </div>
  </dialog>`}function ft(e,t,o=!1){!o&&e.target===e.currentTarget&&t()}function yt(e,t,o=!1){o?e.preventDefault():t()}function ml(e){let t=e.removeModal,o=()=>e.tools.closeRemoveDeviceModal();if(!t.open)return l`<dialog
      id="latter-rm-modal"
      aria-labelledby="latter-rm-title"
      @cancel=${a=>yt(a,o,t.busy)}
      @click=${a=>ft(a,o,t.busy)}
      class="studio-dialog confirm-dialog"
    >
      ${v}
    </dialog>`;let i=t.title||"Device";return l`<dialog
    id="latter-rm-modal"
    aria-labelledby="latter-rm-title"
    aria-describedby="latter-rm-desc"
    @cancel=${a=>yt(a,o,t.busy)}
    @click=${a=>ft(a,o,t.busy)}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-rm-title" class="dialog-title">
          ${e.t("confirm.remove_device.title",{title:i})}
        </h3>
        <span class="chip chip-warning confirm-blast-badge">
          ${e.t("confirm.blast_radius_one")}
        </span>
      </div>
      <p id="latter-rm-desc" class="dialog-text">
        ${e.t("confirm.remove_device.body",{title:i})}
      </p>
      <div class="dialog-actions with-secondary">
        <button
          type="button"
          ?disabled=${t.busy||!t.subentryId}
          @click=${()=>{e.tools.exportBackup(t.subentryId)}}
          class="btn btn-text btn-compact"
        >
          ${e.t("action.download_backup_first")}
        </button>
        <div class="dialog-actions-end">
          <button type="button" ?disabled=${t.busy} @click=${o} class="btn btn-secondary">
            ${e.t("action.cancel")}
          </button>
          <button
            type="button"
            ?disabled=${t.busy}
            @click=${()=>{e.tools.confirmRemoveDevice()}}
            class="btn btn-danger-filled"
          >
            ${e.t("confirm.remove_device.confirm")}
          </button>
        </div>
      </div>
    </div>
  </dialog>`}function gl(e){let t=e.resetModal,o=()=>e.tools.closeResetDeviceModal();return t.open?l`<dialog
    id="latter-reset-modal"
    aria-labelledby="latter-reset-title"
    aria-describedby="latter-reset-desc"
    @cancel=${i=>yt(i,o,t.busy)}
    @click=${i=>ft(i,o,t.busy)}
    class="studio-dialog confirm-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-reset-title" class="dialog-title">
          ${e.t("confirm.reset_device.title")}
        </h3>
        <span class="chip chip-warning confirm-blast-badge">
          ${e.t("confirm.blast_radius_one")}
        </span>
      </div>
      <div class="settings-list">
        ${j({id:"latter-reset-device-settings",label:e.t("confirm.reset_device.device_settings"),description:e.t("confirm.reset_device.device_settings_desc"),disabled:t.busy,checked:t.deviceSettings,onChange:i=>{e.resetModal={...e.resetModal,deviceSettings:i},e.host.requestUpdate()}})}
        ${j({id:"latter-reset-latter-options",label:e.t("confirm.reset_device.latter_options"),description:e.t("confirm.reset_device.latter_options_desc"),disabled:t.busy,checked:t.latterOptions,onChange:i=>{e.resetModal={...e.resetModal,latterOptions:i},e.host.requestUpdate()}})}
      </div>
      <p id="latter-reset-desc" class="dialog-text">
        ${e.t("confirm.reset_device.body")}
      </p>
      <div class="dialog-actions with-secondary">
        <button
          type="button"
          ?disabled=${t.busy||!e.activeSubentryId}
          @click=${()=>{e.tools.exportBackup(e.activeSubentryId)}}
          class="btn btn-text btn-compact"
        >
          ${e.t("action.download_backup_first")}
        </button>
        <div class="dialog-actions-end">
          <button type="button" ?disabled=${t.busy} @click=${o} class="btn btn-secondary">
            ${e.t("action.cancel")}
          </button>
          <button
            type="button"
            id="latter-reset-confirm-btn"
            ?disabled=${t.busy||!t.deviceSettings&&!t.latterOptions}
            @click=${()=>{e.tools.confirmResetDevice()}}
            class="btn btn-danger-filled"
          >
            ${e.t("confirm.reset_device.confirm")}
          </button>
        </div>
      </div>
    </div>
  </dialog>`:l`<dialog
      id="latter-reset-modal"
      aria-labelledby="latter-reset-title"
      @cancel=${i=>yt(i,o,t.busy)}
      @click=${i=>ft(i,o,t.busy)}
      class="studio-dialog confirm-dialog"
    >
      ${v}
    </dialog>`}function _l(e){let t=e.addBleModal,o=()=>e.tools.closeAddBleModal();if(!t.open)return l`<dialog
      id="latter-add-dev-modal"
      aria-labelledby="latter-add-dev-title"
      @cancel=${n=>yt(n,o,t.busy)}
      @click=${n=>ft(n,o,t.busy)}
      class="studio-dialog"
    >
      ${v}
    </dialog>`;let i=e.state?.catalog?.persons||[],a=e.state?.discovered_ble_devices||[];return l`<dialog
    id="latter-add-dev-modal"
    aria-labelledby="latter-add-dev-title"
    @cancel=${n=>yt(n,o,t.busy)}
    @click=${n=>ft(n,o,t.busy)}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-add-dev-title" class="dialog-title">${e.t("dialogs.ble_title")}</h3>
      <p class="dialog-text">${e.t("dialogs.ble_body")}</p>
      <div class="stacked-field">
        <label for="ble-candidate-picker">${e.t("dialogs.ble_discovered_label")}</label>
        <select
          id="ble-candidate-picker"
          .value=${S(t.candidateAddr)}
          @change=${n=>e.tools.selectBleCandidateInModal(n.currentTarget.value)}
        >
          <option value="" .selected=${S(!t.candidateAddr)}>
            ${e.t("dialogs.ble_enter_manually")}
          </option>
          ${a.map(n=>{let s=n.target_address||"",r=n.label||`${n.title||s}${n.area_name?` (${n.area_name})`:""}`;return l`<option value=${s} .selected=${S(s===t.candidateAddr)}>
              ${r}
            </option>`})}
        </select>
      </div>
      <div class="stacked-field">
        <label for="ble-custom-name">${e.t("dialogs.ble_name_label")}</label>
        <input
          type="text"
          id="ble-custom-name"
          placeholder=${e.t("dialogs.ble_name_placeholder")}
          .value=${V(t.name)}
          @input=${n=>{e.addBleModal={...e.addBleModal,name:n.currentTarget.value}}}
        />
      </div>
      <div class="stacked-field">
        <label for="ble-custom-addr">${e.t("dialogs.ble_addr_label")}</label>
        <input
          type="text"
          id="ble-custom-addr"
          placeholder=${e.t("dialogs.ble_addr_placeholder")}
          .value=${V(t.address)}
          @input=${n=>{e.addBleModal={...e.addBleModal,address:n.currentTarget.value}}}
          class="mono"
        />
        <span class="help-text">${e.t("dialogs.ble_addr_help")}</span>
      </div>
      <div class="stacked-field">
        <label for="ble-custom-person">${e.t("dialogs.ble_person_label")}</label>
        <select
          id="ble-custom-person"
          .value=${S(t.assignedPerson)}
          @change=${n=>{e.addBleModal={...e.addBleModal,assignedPerson:n.currentTarget.value}}}
        >
          ${Ne(i,t.assignedPerson,e.t("common.unassigned"))}
        </select>
      </div>
      <div class="dialog-actions">
        <button type="button" ?disabled=${t.busy} @click=${o} class="btn btn-secondary">
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          ?disabled=${t.busy}
          @click=${()=>{e.tools.confirmAddBleModal()}}
          class="btn btn-primary"
        >
          ${e.t("action.add_ble_tag")}
        </button>
      </div>
    </div>
  </dialog>`}function hl(e){let t=e.saveGroupModal,o=()=>e.groups.closeSaveGroupModal();return t.open?l`<dialog
    id="latter-save-group-modal"
    aria-labelledby="latter-save-group-title"
    @cancel=${i=>yt(i,o,!!t.busy)}
    @click=${i=>ft(i,o,!!t.busy)}
    class="studio-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-save-group-title" class="dialog-title">
        ${e.t("dialogs.save_group_title")}
      </h3>
      <p class="dialog-text">${e.t("dialogs.save_group_body")}</p>
      <div class="stacked-field">
        <label for="save-group-name">${e.t("groups.group_name")}</label>
        <input
          type="text"
          id="save-group-name"
          placeholder=${e.t("dialogs.save_group_name_placeholder")}
          .value=${V(t.name)}
          @input=${i=>{e.saveGroupModal={...e.saveGroupModal,name:i.currentTarget.value}}}
        />
      </div>
      <div class="stacked-field">
        <label for="save-group-desc">${e.t("groups.description_optional")}</label>
        <input
          type="text"
          id="save-group-desc"
          placeholder=${e.t("dialogs.save_group_desc_placeholder")}
          .value=${V(t.description)}
          @input=${i=>{e.saveGroupModal={...e.saveGroupModal,description:i.currentTarget.value}}}
        />
      </div>
      <div class="settings-list">
        ${j({id:"save-group-include-display",label:e.t("groups.include_display"),description:e.t("groups.include_display_desc"),checked:!!t.includeDisplay,onChange:i=>{e.saveGroupModal={...e.saveGroupModal,includeDisplay:i},e.host.requestUpdate()}})}
        ${j({id:"save-group-include-interface",label:e.t("groups.include_interface"),description:e.t("groups.include_interface_desc"),checked:!!t.includeInterface,onChange:i=>{e.saveGroupModal={...e.saveGroupModal,includeInterface:i},e.host.requestUpdate()}})}
      </div>
      <div class="dialog-actions">
        <button type="button" ?disabled=${!!t.busy} @click=${o} class="btn btn-secondary">
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          id="latter-save-group-confirm-btn"
          ?disabled=${!!t.busy}
          @click=${()=>{e.groups.confirmSaveGroupModal()}}
          class="btn btn-primary"
        >
          ${e.t("action.save_group")}
        </button>
      </div>
    </div>
  </dialog>`:l`<dialog
      id="latter-save-group-modal"
      aria-labelledby="latter-save-group-title"
      @cancel=${i=>yt(i,o,!!t.busy)}
      @click=${i=>ft(i,o,!!t.busy)}
      class="studio-dialog"
    >
      ${v}
    </dialog>`}var Ld="M10,4H4C2.89,4 2,4.89 2,6V18A2,2 0 0,0 4,20H20A2,2 0 0,0 22,18V8C22,6.89 21.1,6 20,6H12L10,4Z";function vl(e){let t=e.mediaImportModal,o=()=>e.entity.closeMediaImportModal(),i=g=>{g.target===g.currentTarget&&!t.importing&&o()};if(!t.open)return l`<dialog
      id="latter-media-import-modal"
      aria-labelledby="latter-media-import-title"
      @cancel=${g=>{t.importing?g.preventDefault():o()}}
      @click=${i}
      class="studio-dialog photo-dialog"
    >
      ${v}
    </dialog>`;let a=e.state?.photo_collections||[],n=t.images.filter(g=>!g.too_large),s=new Set(t.selectedPaths),r=n.length>0&&n.every(g=>s.has(g.relpath)),c=t.subpath?t.subpath.split("/").filter(Boolean):[],u=(c.length>0?c[c.length-1]:void 0)??(t.root||"Media"),p=g=>{let _=s.has(g)?t.selectedPaths.filter(h=>h!==g):[...t.selectedPaths,g];e.mediaImportModal={...e.mediaImportModal,selectedPaths:_},e.host.requestUpdate()},d=()=>{let g=r?[]:n.map(_=>_.relpath);e.mediaImportModal={...e.mediaImportModal,selectedPaths:g},e.host.requestUpdate()},m=t.importing?e.t("media_import.importing_btn"):t.selectedPaths.length===1?e.t("media_import.import_btn_one"):e.t("media_import.import_btn_many",{count:A(t.selectedPaths.length,e.hass,0)});return l`<dialog
    id="latter-media-import-modal"
    aria-labelledby="latter-media-import-title"
    @cancel=${g=>{t.importing?g.preventDefault():o()}}
    @click=${i}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-media-import-title" class="dialog-title">
          ${e.t("media_import.title")}
        </h3>
        ${t.roots.length>1?l`<select
              id="media-import-root-select"
              aria-label=${e.t("media_import.root_label")}
              ?disabled=${t.loading||t.importing}
              .value=${S(t.root)}
              @change=${g=>{e.entity.browseMediaFolder(g.currentTarget.value,"")}}
            >
              ${t.roots.map(g=>l`<option value=${g.id} .selected=${S(g.id===t.root)}>
                  ${g.name}
                </option>`)}
            </select>`:v}
      </div>

      <p class="dialog-text">${e.t("media_import.subtitle")}</p>

      ${t.error?l`<div role="alert" class="alert alert-error">
            <span>${t.error}</span>
          </div>`:v}

      ${t.roots.length>0?l`<div class="media-breadcrumbs" aria-label=${e.t("media_import.root_label")}>
            ${t.parentSubpath!==null?l`<button
                  type="button"
                  id="btn-media-up"
                  ?disabled=${t.loading||t.importing}
                  @click=${()=>{e.entity.browseMediaFolder(t.root,t.parentSubpath||"")}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("media_import.up_folder")}
                </button>`:v}
            <button
              type="button"
              ?disabled=${t.loading||t.importing||!t.subpath}
              @click=${()=>{e.entity.browseMediaFolder(t.root,"")}}
              class="btn btn-text btn-compact"
            >
              ${t.roots.find(g=>g.id===t.root)?.name||t.root}
            </button>
            ${c.map((g,_)=>{let h=c.slice(0,_+1).join("/"),b=_===c.length-1;return l`<span aria-hidden="true">/</span>
                <button
                  type="button"
                  ?disabled=${t.loading||t.importing||b}
                  @click=${()=>{e.entity.browseMediaFolder(t.root,h)}}
                  class="btn btn-text btn-compact"
                >
                  ${g}
                </button>`})}
            ${n.length>0?l`<button
                  type="button"
                  id="btn-media-select-all"
                  ?disabled=${t.loading||t.importing}
                  @click=${d}
                  class="btn btn-secondary btn-compact"
                >
                  ${r?e.t("media_import.clear_folder_selection"):e.t("media_import.select_all_folder")}
                </button>`:v}
          </div>`:v}

      <div class="media-scroll-area">
        ${t.loading?l`<div role="status" class="loading-state">${e.t("common.loading")}</div>`:t.roots.length===0&&!t.error?l`<p class="empty-state">${e.t("media_import.empty_roots")}</p>`:t.folders.length===0&&t.images.length===0?l`<p class="empty-state">${e.t("media_import.empty_folder")}</p>`:l`${t.folders.length>0?l`<div class="media-folder-list">
                        ${t.folders.map(g=>l`<button
                            type="button"
                            ?disabled=${t.importing}
                            @click=${()=>{e.entity.browseMediaFolder(t.root,g.subpath)}}
                            class="media-folder-btn"
                          >
                            ${we(Ld)}
                            <span>${g.name}</span>
                          </button>`)}
                      </div>`:v}
                  ${t.images.length>0?l`<div class="photo-grid">
                        ${t.images.map(g=>{let _=s.has(g.relpath);return l`<div class="photo-tile ${_?"selected":""}">
                            <input
                              type="checkbox"
                              aria-label=${g.name}
                              ?disabled=${g.too_large||t.importing}
                              .checked=${S(_)}
                              @change=${()=>p(g.relpath)}
                              class="photo-tile-check"
                            />
                            <button
                              type="button"
                              ?disabled=${g.too_large||t.importing}
                              @click=${()=>p(g.relpath)}
                              class="photo-tile-thumb-btn"
                            >
                              ${g.thumb_url?l`<img
                                    src=${g.thumb_url}
                                    alt=${g.name}
                                    loading="lazy"
                                    class="photo-tile-img"
                                  />`:v}
                              ${g.too_large?l`<span class="photo-tile-badge">
                                    ${e.t("media_import.too_large")}
                                  </span>`:g.already_imported?l`<span class="photo-tile-badge">
                                      ${e.t("media_import.already_imported")}
                                    </span>`:v}
                            </button>
                            <div class="photo-tile-meta">
                              <span class="photo-tile-name">${g.name}</span>
                            </div>
                          </div>`})}
                      </div>`:v}`}
      </div>

      ${t.images.length>0?l`<div class="stack">
            <div class="input-action-row">
              <select
                id="media-import-collection"
                aria-label=${e.t("media_import.collection_label")}
                ?disabled=${t.importing||t.useNewFolderCollection}
                .value=${S(t.collectionId)}
                @change=${g=>{e.mediaImportModal={...e.mediaImportModal,collectionId:g.currentTarget.value},e.host.requestUpdate()}}
              >
                <option value="" .selected=${S(!t.collectionId)}>
                  ${e.t("photo_upload.no_collection")}
                </option>
                ${a.map(g=>l`<option value=${g.id} .selected=${S(t.collectionId===g.id)}>
                    ${g.name}
                  </option>`)}
              </select>
              <button
                type="button"
                id="btn-media-new-col-from-folder"
                ?disabled=${t.importing}
                @click=${()=>{let g=!t.useNewFolderCollection;e.mediaImportModal={...e.mediaImportModal,useNewFolderCollection:g,newCollectionName:g?u:""},e.host.requestUpdate()}}
                class="btn ${t.useNewFolderCollection?"btn-primary":"btn-secondary"} btn-compact"
              >
                ${e.t("media_import.new_from_folder")}
              </button>
            </div>
            ${t.useNewFolderCollection?l`<div class="stacked-field">
                  <label for="media-import-new-col-name">
                    ${e.t("media_import.new_collection_name")}
                  </label>
                  <input
                    type="text"
                    id="media-import-new-col-name"
                    ?disabled=${t.importing}
                    .value=${V(t.newCollectionName)}
                    @input=${g=>{e.mediaImportModal={...e.mediaImportModal,newCollectionName:g.currentTarget.value}}}
                  />
                </div>`:v}
          </div>`:v}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${t.importing}
          @click=${o}
          class="btn btn-secondary"
        >
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-media-import-confirm"
          ?disabled=${t.importing||t.selectedPaths.length===0}
          @click=${()=>{e.entity.importSelectedMedia()}}
          class="btn btn-primary"
        >
          ${m}
        </button>
      </div>
    </div>
  </dialog>`}function bl(e){let t=e.photoPickerModal,o=()=>e.entity.closePhotoPickerModal(),i=f=>{f.target===f.currentTarget&&!t.busy&&o()},a=f=>{t.busy?f.preventDefault():o()};if(!t.open)return l`<dialog
      id="latter-photo-picker-modal"
      aria-labelledby="latter-photo-picker-title"
      @cancel=${a}
      @click=${i}
      class="studio-dialog photo-dialog"
    >
      ${v}
    </dialog>`;let n=t.target==="screensaver",s=String(e.state?.config?.display_shape||"square")==="circle"?"circle":"",r=(e.state?.wallpapers&&e.state.wallpapers.length>0?e.state.wallpapers:e.state?.system_wallpapers)||[],c=e.state?.photo_collections||[],u=oo(r,t.filterCollection,t.search,{excludeDynamic:n}),p=oo(r,t.collectionId||de,"",{excludeDynamic:n}),d=Ci(t.selectedIds,r,n),m=new Set(d),g=f=>{let k=m.has(f)?d.filter(w=>w!==f):[...d,f];e.photoPickerModal={...e.photoPickerModal,selectedIds:k},e.host.requestUpdate()},_=!t.busy&&(t.mode==="collection"?!!t.collectionId:d.length>0),h=n?e.t("photo_picker.title_screensaver"):e.t("photo_picker.title_wallpaper"),b=[{id:de,label:e.t("photos.filter_all")},{id:Ye,label:e.t("photos.filter_defaults")},{id:Ze,label:e.t("photos.filter_my_photos")},{id:mt,label:e.t("photos.filter_uncategorized")}],y=()=>{let f=t.target,k=t.mode,w=[...d],M=t.collectionId;o(),e.entity.openPhotoUploadModal({defaultCollectionId:M.startsWith("col_")?M:"",onComplete:E=>{e.entity.openPhotoPickerModal(f),E.length>0&&k==="photos"&&(e.photoPickerModal={...e.photoPickerModal,mode:"photos",selectedIds:Array.from(new Set([...w,...E]))},e.host.requestUpdate())}})};return l`<dialog
    id="latter-photo-picker-modal"
    aria-labelledby="latter-photo-picker-title"
    @cancel=${a}
    @click=${i}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-picker-title" class="dialog-title">${h}</h3>
        <button
          type="button"
          id="btn-picker-quick-upload"
          ?disabled=${t.busy}
          @click=${y}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("photos.upload_btn")}
        </button>
      </div>

      <div
        role="radiogroup"
        aria-label=${e.t("photo_picker.mode_aria")}
        class="segmented"
      >
        <button
          type="button"
          id="btn-picker-mode-photos"
          role="radio"
          aria-checked=${t.mode==="photos"?"true":"false"}
          @click=${()=>{e.photoPickerModal={...e.photoPickerModal,mode:"photos"},e.host.requestUpdate()}}
          class=${t.mode==="photos"?"active":""}
        >
          ${e.t("photo_picker.mode_photos")}
        </button>
        <button
          type="button"
          id="btn-picker-mode-collection"
          role="radio"
          aria-checked=${t.mode==="collection"?"true":"false"}
          @click=${()=>{e.photoPickerModal={...e.photoPickerModal,mode:"collection"},e.host.requestUpdate()}}
          class=${t.mode==="collection"?"active":""}
        >
          ${e.t("photo_picker.mode_collection")}
        </button>
      </div>

      ${t.mode==="collection"?l`<div class="stack">
            <div class="stacked-field">
              <label for="photo-picker-collection-select">
                ${e.t("photo_picker.collection_label")}
              </label>
              <select
                id="photo-picker-collection-select"
                .value=${S(t.collectionId)}
                @change=${f=>{e.photoPickerModal={...e.photoPickerModal,collectionId:f.currentTarget.value},e.host.requestUpdate()}}
              >
                ${b.map(f=>l`<option value=${f.id} .selected=${S(t.collectionId===f.id)}>
                    ${f.label}
                  </option>`)}
                ${c.map(f=>l`<option value=${f.id} .selected=${S(t.collectionId===f.id)}>
                    ${f.name} (${A(f.count,e.hass,0)})
                  </option>`)}
              </select>
            </div>
            <div class="photo-pool-preview">
              ${p.length>0?l`<div class="photo-pool-thumbs">
                    ${p.slice(0,5).map(f=>l`<img
                        src=${f.thumb_url||f.preview_url||""}
                        alt=${f.name||f.id}
                        loading="lazy"
                        class="photo-pool-thumb ${s}"
                      />`)}
                  </div>`:v}
              <div class="photo-pool-info">
                <span class="photo-pool-title">
                  ${Ti(e,t.collectionId)}
                </span>
                <span class="photo-pool-meta">
                  ${p.length===1?e.t("sys_overview.photos_count_one"):e.t("sys_overview.photos_count_many",{count:A(p.length,e.hass,0)})}
                </span>
              </div>
            </div>
          </div>`:l`<div class="stack">
            <div class="photo-toolbar">
              <input
                type="search"
                id="photo-picker-search"
                aria-label=${e.t("photos.search_aria")}
                placeholder=${e.t("photos.search_placeholder")}
                .value=${V(t.search)}
                @input=${f=>{e.photoPickerModal={...e.photoPickerModal,search:f.currentTarget.value},e.host.requestUpdate()}}
                class="photo-search-input"
              />
              <select
                id="photo-picker-filter-col"
                aria-label=${e.t("photo_picker.collection_label")}
                .value=${S(t.filterCollection)}
                @change=${f=>{e.photoPickerModal={...e.photoPickerModal,filterCollection:f.currentTarget.value},e.host.requestUpdate()}}
              >
                ${b.map(f=>l`<option value=${f.id} .selected=${S(t.filterCollection===f.id)}>
                    ${f.label}
                  </option>`)}
                ${c.map(f=>l`<option
                    value=${f.id}
                    .selected=${S(t.filterCollection===f.id)}
                  >
                    ${f.name}
                  </option>`)}
              </select>
            </div>

            <div class="photo-toolbar">
              <span class="row-description">${e.t("photo_picker.custom_hint")}</span>
              <span class="chip chip-primary">
                ${d.length===1?e.t("photo_picker.custom_selected_one"):e.t("photo_picker.custom_selected_many",{count:A(d.length,e.hass,0)})}
              </span>
              ${d.length>0?l`<button
                    type="button"
                    id="btn-picker-clear-custom"
                    ?disabled=${t.busy}
                    @click=${()=>{e.photoPickerModal={...e.photoPickerModal,selectedIds:[]},e.host.requestUpdate()}}
                    class="btn btn-text btn-compact"
                  >
                    ${e.t("photos.clear_selection")}
                  </button>`:v}
            </div>

            ${u.length===0?l`<p class="empty-state">${e.t("photo_picker.empty")}</p>`:l`<div class="photo-picker-grid">
                  ${u.map(f=>{let k=m.has(f.id),w=f.thumb_url||f.preview_url||"";return l`<button
                      type="button"
                      data-photo-id=${f.id}
                      aria-pressed=${k?"true":"false"}
                      @click=${()=>g(f.id)}
                      class="photo-picker-item ${k?"selected":""}"
                    >
                      ${w?l`<img
                            src=${w}
                            alt=${f.name||f.id}
                            loading="lazy"
                            class="photo-picker-thumb ${s}"
                          />`:l`<div class="photo-picker-thumb ${s}" aria-hidden="true"></div>`}
                      <span class="photo-picker-name">${f.name||f.id}</span>
                      ${lt(f)?l`<span class="chip chip-primary">
                            ${e.t("photos.badge_dynamic")}
                          </span>`:v}
                    </button>`})}
                </div>`}
          </div>`}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${t.busy}
          @click=${o}
          class="btn btn-secondary"
        >
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-picker-apply"
          ?disabled=${!_}
          @click=${()=>{e.entity.applyPhotoPickerModal()}}
          class="btn btn-primary"
        >
          ${e.t("photo_picker.apply_btn")}
        </button>
      </div>
    </div>
  </dialog>`}var Nt=new Map,Od=32;function rn(e,t){if(!e||typeof Image>"u")return null;let o=Nt.get(e);if(o)return o.complete&&o.naturalWidth>0?o:null;if(Nt.size>=Od){let a=Nt.keys().next().value;a&&Nt.delete(a)}let i=new Image;return i.crossOrigin="anonymous",i.onload=()=>{t()},i.src=e,Nt.set(e,i),i.complete&&i.naturalWidth>0?i:null}var ln=new WeakMap;function fl(e,t){if(t.photoUploadModal.open&&t.photoUploadModal.files.length>0){let o=t.photoUploadModal,i=o.files[o.activeIndex]||o.files[0],a=e.getElementById("latter-upload-crop-canvas");if(a&&i){let n=rn(i.objectUrl,()=>t.host.requestUpdate());n&&(i.width!==n.naturalWidth||i.height!==n.naturalHeight)&&(i.width=n.naturalWidth,i.height=n.naturalHeight),wi(a,n,i.crop,o.previewAspect,{showGuides:!0})}for(let n=0;n<o.files.length;n+=1){let s=o.files[n];if(!s)continue;let r=e.getElementById(`latter-upload-thumb-${s.id}`);if(!r)continue;let c=rn(s.objectUrl,()=>t.host.requestUpdate());wi(r,c,s.crop,"square",{showGuides:!1})}}if(t.photoEditModal.open&&t.photoEditModal.photoId){let o=t.photoEditModal,i=(t.state?.system_wallpapers||[]).find(n=>n.id===o.photoId),a=e.getElementById("latter-edit-crop-canvas");if(a&&i){let n=i.orig_url||i.thumb_url||i.preview_url||"",s=rn(n,()=>t.host.requestUpdate());wi(a,s,o.crop,o.previewAspect,{showGuides:!0})}}}function yl(e,t,o,i){return{onPointerDown:a=>{if(i)return;let n=a,s=n.currentTarget;s.setPointerCapture?.(n.pointerId),s.classList.add("dragging"),ln.set(s,{pointerId:n.pointerId,lastX:n.clientX,lastY:n.clientY})},onPointerMove:a=>{if(i)return;let n=a,s=n.currentTarget,r=ln.get(s);if(!r||r.pointerId!==n.pointerId)return;let c=n.clientX-r.lastX,u=n.clientY-r.lastY;r.lastX=n.clientX,r.lastY=n.clientY;let p=s.getBoundingClientRect(),d=p.width>0?s.width/p.width:1,m=p.height>0?s.height/p.height:1,g=t(),_=Ns(e(),c*d,u*m,g.width||s.width,g.height||s.height,s.width,s.height);o(_)},onPointerUp:a=>{let n=a,s=n.currentTarget;ln.delete(s),s.classList.remove("dragging"),s.hasPointerCapture?.(n.pointerId)&&s.releasePointerCapture(n.pointerId)}}}function wl(e,t,o){let i=[{id:"square",label:e.t("photo_edit.aspect_square")},{id:"round",label:e.t("photo_edit.aspect_round")},{id:"widescreen",label:e.t("photo_edit.aspect_widescreen")}];return l`<div
    role="radiogroup"
    aria-label=${e.t("photo_edit.aspect_aria")}
    class="segmented"
  >
    ${i.map(a=>l`<button
        type="button"
        role="radio"
        aria-checked=${t===a.id?"true":"false"}
        @click=${()=>o(a.id)}
        class=${t===a.id?"active":""}
      >
        ${a.label}
      </button>`)}
  </div>`}function Sl(e){let t=e.photoUploadModal,o=!!(t.uploading||t.creatingCollection),i=()=>e.entity.closePhotoUploadModal(),a=y=>{y.target===y.currentTarget&&!o&&i()};if(!t.open)return l`<dialog
      id="latter-photo-upload-modal"
      aria-labelledby="latter-photo-upload-title"
      @cancel=${y=>{o?y.preventDefault():i()}}
      @click=${a}
      class="studio-dialog photo-dialog"
    >
      ${v}
    </dialog>`;let n=e.state?.photo_collections||[],s=t.files[t.activeIndex]||t.files[0]||null,r=Va(t.previewAspect),c=`--upload-pct:${t.currentPercent}%`,u=y=>{if(!s)return;let f=t.files.map((k,w)=>w===t.activeIndex?{...k,...y}:k);e.photoUploadModal={...e.photoUploadModal,files:f},e.host.requestUpdate()},p=yl(()=>s?.crop||{...rt},()=>{let y=s?.objectUrl?Nt.get(s.objectUrl):null;return{width:y?.naturalWidth||s?.width||r.width,height:y?.naturalHeight||s?.height||r.height}},y=>u({crop:y}),t.uploading),d=y=>{let f=y.currentTarget;f.files&&f.files.length>0&&(e.entity.stageUploadFiles(f.files),f.value="")},m=y=>{y.currentTarget?.closest(".dialog-body")?.querySelector("#input-photo-upload-files")?.click()},g=y=>{y.preventDefault(),e.photoUploadModal.draggingFiles||(e.photoUploadModal={...e.photoUploadModal,draggingFiles:!0},e.host.requestUpdate())},_=()=>{e.photoUploadModal.draggingFiles&&(e.photoUploadModal={...e.photoUploadModal,draggingFiles:!1},e.host.requestUpdate())},h=y=>{y.preventDefault();let f=y;e.photoUploadModal={...e.photoUploadModal,draggingFiles:!1},f.dataTransfer?.files&&f.dataTransfer.files.length>0?e.entity.stageUploadFiles(f.dataTransfer.files):e.host.requestUpdate()},b=t.files.length===1?e.t("photo_upload.upload_all_one"):e.t("photo_upload.upload_all_many",{count:A(t.files.length,e.hass,0)});return l`<dialog
    id="latter-photo-upload-modal"
    aria-labelledby="latter-photo-upload-title"
    @cancel=${y=>{o?y.preventDefault():i()}}
    @click=${a}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-upload-title" class="dialog-title">
          ${e.t("photo_upload.title")}
        </h3>
        ${t.files.length>0&&!t.uploading?l`<button
              type="button"
              id="btn-upload-add-more"
              @click=${m}
              class="btn btn-secondary btn-compact"
            >
              ${e.t("photo_upload.add_more")}
            </button>`:v}
      </div>

      <input
        type="file"
        id="input-photo-upload-files"
        accept="image/*"
        multiple
        aria-label=${e.t("photo_upload.choose_files")}
        @change=${d}
        class="offscreen"
      />

      ${t.files.length===0?l`<div
            id="photo-upload-dropzone"
            role="button"
            tabindex="0"
            @click=${m}
            @keydown=${y=>{(y.key==="Enter"||y.key===" ")&&(y.preventDefault(),m(y))}}
            @dragover=${g}
            @dragleave=${_}
            @drop=${h}
            class="crop-dropzone ${t.draggingFiles?"dragging":""}"
          >
            <strong>${e.t("photo_upload.dropzone_title")}</strong>
            <span class="row-description">${e.t("photo_upload.dropzone_hint")}</span>
            <span class="btn btn-primary btn-compact">${e.t("photo_upload.choose_files")}</span>
          </div>`:l`<div
            class="crop-stage-wrap"
            @dragover=${g}
            @dragleave=${_}
            @drop=${h}
          >
            ${wl(e,t.previewAspect,y=>{e.photoUploadModal={...e.photoUploadModal,previewAspect:y},e.host.requestUpdate()})}

            <canvas
              id="latter-upload-crop-canvas"
              width=${String(r.width)}
              height=${String(r.height)}
              @pointerdown=${p.onPointerDown}
              @pointermove=${p.onPointerMove}
              @pointerup=${p.onPointerUp}
              @pointercancel=${p.onPointerUp}
              class="crop-canvas ${t.previewAspect==="round"?"round":""}"
            ></canvas>

            <p class="row-description">${e.t("photo_edit.crop_hint")}</p>

            <div class="crop-controls-row">
              <div class="crop-zoom-control">
                <label for="upload-crop-zoom">${e.t("photo_edit.zoom_label")}</label>
                <input
                  type="range"
                  id="upload-crop-zoom"
                  min="1"
                  max="3"
                  step="0.05"
                  ?disabled=${t.uploading}
                  .value=${S(String(s?.crop.zoom??1))}
                  @input=${y=>{let f=Number(y.currentTarget.value)||1;u({crop:vt({...s?.crop||rt,zoom:f})})}}
                />
                <span class="kv-value">${(s?.crop.zoom??1).toFixed(2)}×</span>
              </div>
              <button
                type="button"
                id="btn-upload-reset-crop"
                ?disabled=${t.uploading}
                @click=${()=>u({crop:{...rt}})}
                class="btn btn-text btn-compact"
              >
                ${e.t("photo_edit.reset_crop")}
              </button>
            </div>
          </div>

          <div class="stacked-field">
            <label for="upload-photo-name">${e.t("photo_edit.name_label")}</label>
            <input
              type="text"
              id="upload-photo-name"
              placeholder=${e.t("photo_edit.name_placeholder")}
              ?disabled=${t.uploading}
              .value=${V(s?.name||"")}
              @input=${y=>u({name:y.currentTarget.value})}
            />
          </div>

          ${t.files.length>1?l`<div class="crop-filmstrip" role="list">
                ${t.files.map((y,f)=>l`<div
                    role="listitem"
                    class="crop-filmstrip-item ${f===t.activeIndex?"active":""}"
                  >
                    <button
                      type="button"
                      aria-label=${e.t("photo_upload.select_staged_aria",{name:y.name})}
                      ?disabled=${t.uploading}
                      @click=${()=>{e.photoUploadModal={...e.photoUploadModal,activeIndex:f},e.host.requestUpdate()}}
                      class="crop-filmstrip-btn"
                    >
                      <canvas
                        id=${`latter-upload-thumb-${y.id}`}
                        width="56"
                        height="56"
                        class="crop-filmstrip-thumb"
                      ></canvas>
                    </button>
                    ${t.uploading?v:l`<button
                          type="button"
                          aria-label=${e.t("photo_upload.remove_staged_aria",{name:y.name})}
                          @click=${()=>e.entity.removeStagedUpload(f)}
                          class="crop-filmstrip-remove"
                        >
                          ×
                        </button>`}
                  </div>`)}
              </div>`:v}

          <div class="stacked-field">
            <label for="upload-photo-collection">${e.t("photo_upload.collection_label")}</label>
            <div class="input-action-row">
              <select
                id="upload-photo-collection"
                ?disabled=${t.uploading||t.creatingCollection}
                .value=${S(t.collectionId)}
                @change=${y=>{e.photoUploadModal={...e.photoUploadModal,collectionId:y.currentTarget.value},e.host.requestUpdate()}}
              >
                <option value="" .selected=${S(!t.collectionId)}>
                  ${e.t("photo_upload.no_collection")}
                </option>
                ${n.map(y=>l`<option value=${y.id} .selected=${S(t.collectionId===y.id)}>
                    ${y.name}
                  </option>`)}
              </select>
              ${t.newCollectionOpen?v:l`<button
                    type="button"
                    id="btn-upload-new-collection"
                    ?disabled=${t.uploading||t.creatingCollection}
                    @click=${()=>{e.photoUploadModal={...e.photoUploadModal,newCollectionOpen:!0,newCollectionName:""},e.host.requestUpdate()}}
                    class="btn btn-secondary btn-compact"
                  >
                    ${e.t("photos.new_collection_btn")}
                  </button>`}
            </div>
            ${t.newCollectionOpen?l`<div class="input-action-row">
                  <input
                    type="text"
                    id="input-upload-new-collection-name"
                    aria-label=${e.t("photos.new_collection_btn")}
                    placeholder=${e.t("photos.new_collection_placeholder")}
                    ?disabled=${t.uploading||t.creatingCollection}
                    .value=${V(t.newCollectionName)}
                    @input=${y=>{e.photoUploadModal={...e.photoUploadModal,newCollectionName:y.currentTarget.value},e.host.requestUpdate()}}
                    @keydown=${y=>{y.key==="Enter"?(y.preventDefault(),e.entity.createUploadCollection()):y.key==="Escape"&&(y.preventDefault(),y.stopPropagation(),e.photoUploadModal={...e.photoUploadModal,newCollectionOpen:!1,newCollectionName:""},e.host.requestUpdate())}}
                  />
                  <button
                    type="button"
                    id="btn-upload-create-collection"
                    ?disabled=${t.uploading||t.creatingCollection||!t.newCollectionName.trim()}
                    @click=${()=>{e.entity.createUploadCollection()}}
                    class="btn btn-secondary btn-compact"
                  >
                    ${e.t("photos.create_collection")}
                  </button>
                  <button
                    type="button"
                    id="btn-upload-cancel-collection"
                    ?disabled=${t.uploading||t.creatingCollection}
                    @click=${()=>{e.photoUploadModal={...e.photoUploadModal,newCollectionOpen:!1,newCollectionName:""},e.host.requestUpdate()}}
                    class="btn btn-text btn-compact"
                  >
                    ${e.t("action.cancel")}
                  </button>
                </div>`:v}
          </div>

          ${t.uploading?l`<div class="stack">
                <div class="photo-upload-status">
                  <span>
                    ${e.t("photo_upload.uploading_progress",{current:A(t.currentIndex,e.hass,0),total:A(t.files.length,e.hass,0),percent:A(t.currentPercent,e.hass,0)})}
                  </span>
                </div>
                <div
                  role="progressbar"
                  aria-label=${e.t("wp_gallery.upload_progress_aria")}
                  aria-valuenow=${String(t.currentPercent)}
                  aria-valuemin="0"
                  aria-valuemax="100"
                  class="upload-progress"
                >
                  <div class="upload-progress-fill" style=${c}></div>
                </div>
              </div>`:v}`}

      <div class="dialog-actions">
        <button
          type="button"
          ?disabled=${t.uploading}
          @click=${i}
          class="btn btn-secondary"
        >
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          id="btn-upload-submit-all"
          ?disabled=${t.uploading||t.files.length===0}
          @click=${()=>{e.entity.uploadAllStagedPhotos()}}
          class="btn btn-primary"
        >
          ${t.uploading?e.t("wp_gallery.uploading"):b}
        </button>
      </div>
    </div>
  </dialog>`}function kl(e){let t=e.photoEditModal,o=()=>e.entity.closePhotoEditModal(),i=d=>{d.target===d.currentTarget&&!t.busy&&o()},a=d=>{t.busy?d.preventDefault():o()};if(!t.open||!t.photoId)return l`<dialog
      id="latter-photo-edit-modal"
      aria-labelledby="latter-photo-edit-title"
      @cancel=${a}
      @click=${i}
      class="studio-dialog photo-dialog"
    >
      ${v}
    </dialog>`;let n=(e.state?.system_wallpapers||[]).find(d=>d.id===t.photoId),s=n?Ge(n):!1,r=e.state?.photo_collections||[],c=Va(t.previewAspect),u=yl(()=>t.crop,()=>{let d=n?.orig_url||n?.thumb_url||n?.preview_url||"",m=d?Nt.get(d):null;return{width:m?.naturalWidth||n?.width||c.width,height:m?.naturalHeight||n?.height||c.height}},d=>{e.photoEditModal={...e.photoEditModal,crop:d},e.host.requestUpdate()},t.busy||!s),p=d=>{let g=t.collections.includes(d)?t.collections.filter(_=>_!==d):[...t.collections,d];e.photoEditModal={...e.photoEditModal,collections:g},e.host.requestUpdate()};return l`<dialog
    id="latter-photo-edit-modal"
    aria-labelledby="latter-photo-edit-title"
    @cancel=${a}
    @click=${i}
    class="studio-dialog photo-dialog"
  >
    <div class="dialog-body">
      <div class="dialog-header-row">
        <h3 id="latter-photo-edit-title" class="dialog-title">
          ${e.t("photo_edit.title")}
        </h3>
        ${n?.width&&n?.height?l`<span class="chip">
              ${e.t("photo_edit.dimensions_meta",{width:A(n.width,e.hass,0),height:A(n.height,e.hass,0)})}
            </span>`:v}
      </div>

      ${s?l`<div class="crop-stage-wrap">
              ${wl(e,t.previewAspect,d=>{e.photoEditModal={...e.photoEditModal,previewAspect:d},e.host.requestUpdate()})}

              <canvas
                id="latter-edit-crop-canvas"
                width=${String(c.width)}
                height=${String(c.height)}
                @pointerdown=${u.onPointerDown}
                @pointermove=${u.onPointerMove}
                @pointerup=${u.onPointerUp}
                @pointercancel=${u.onPointerUp}
                class="crop-canvas ${t.previewAspect==="round"?"round":""}"
              ></canvas>

              <p class="row-description">${e.t("photo_edit.crop_hint")}</p>

              <div class="crop-controls-row">
                <div class="crop-zoom-control">
                  <label for="edit-crop-zoom">${e.t("photo_edit.zoom_label")}</label>
                  <input
                    type="range"
                    id="edit-crop-zoom"
                    min="1"
                    max="3"
                    step="0.05"
                    ?disabled=${t.busy}
                    .value=${S(String(t.crop.zoom))}
                    @input=${d=>{let m=Number(d.currentTarget.value)||1;e.photoEditModal={...e.photoEditModal,crop:vt({...t.crop,zoom:m})},e.host.requestUpdate()}}
                  />
                  <span class="kv-value">${t.crop.zoom.toFixed(2)}×</span>
                </div>
                <button
                  type="button"
                  id="btn-edit-reset-crop"
                  ?disabled=${t.busy}
                  @click=${()=>{e.photoEditModal={...e.photoEditModal,crop:{...rt}},e.host.requestUpdate()}}
                  class="btn btn-text btn-compact"
                >
                  ${e.t("photo_edit.reset_crop")}
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="edit-photo-name">${e.t("photo_edit.name_label")}</label>
              <input
                type="text"
                id="edit-photo-name"
                placeholder=${e.t("photo_edit.name_placeholder")}
                ?disabled=${t.busy}
                .value=${V(t.name)}
                @input=${d=>{e.photoEditModal={...e.photoEditModal,name:d.currentTarget.value}}}
              />
            </div>`:l`<div class="photo-pool-preview">
            ${n?.thumb_url?l`<img
                  src=${n.thumb_url}
                  alt=${n.name||n.id}
                  class="photo-pool-thumb"
                />`:v}
            <div class="photo-pool-info">
              <span class="photo-pool-title">${n?.name||t.photoId}</span>
              <span class="photo-pool-meta">${e.t("wp_gallery.builtin")}</span>
            </div>
          </div>`}

      ${n?.media_source_path?l`<p class="help-text">
            ${e.t("photo_edit.source_media",{path:n.media_source_path})}
          </p>`:v}

      <div class="stacked-field">
        <span class="field-label">${e.t("photo_edit.collections_label")}</span>
        ${r.length>0?l`<div role="group" aria-label=${e.t("photo_edit.collections_label")} class="pill-list">
              ${r.map(d=>{let m=t.collections.includes(d.id);return l`<span class="pill ${m?"enabled":""}">
                  <button
                    type="button"
                    aria-pressed=${m?"true":"false"}
                    ?disabled=${t.busy}
                    @click=${()=>p(d.id)}
                    class="pill-toggle"
                  >
                    ${d.name}
                  </button>
                </span>`})}
            </div>`:l`<p class="row-description">${e.t("photo_edit.collections_empty")}</p>`}
      </div>

      <div class="dialog-actions ${s?"with-secondary":""}">
        ${s?l`<button
              type="button"
              id="btn-edit-delete-photo"
              ?disabled=${t.busy}
              @click=${()=>{let d=t.photoId,m=t.name||n?.name||d;o(),e.entity.requestDeletePhoto(d,m)}}
              class="btn btn-danger"
            >
              ${e.t("action.delete")}
            </button>`:v}
        <div class="dialog-actions-end">
          <button
            type="button"
            ?disabled=${t.busy}
            @click=${o}
            class="btn btn-secondary"
          >
            ${e.t("action.cancel")}
          </button>
          <button
            type="button"
            id="btn-edit-save-photo"
            ?disabled=${t.busy}
            @click=${()=>{e.entity.savePhotoEditModal()}}
            class="btn btn-primary"
          >
            ${e.t("action.save")}
          </button>
        </div>
      </div>
    </div>
  </dialog>`}var $l=[{value:"all",labelKey:"dialogs.sc_icon_style_all"},{value:"solid",labelKey:"dialogs.sc_icon_style_solid"},{value:"outline",labelKey:"dialogs.sc_icon_style_outline"}],Bd={glass:"dialogs.sc_badge_style_glass",inverted:"dialogs.sc_badge_style_inverted"},Nd={default:"dialogs.sc_accent_default",primary:"dialogs.sc_accent_primary",gold:"dialogs.sc_accent_gold",green:"dialogs.sc_accent_green",red:"dialogs.sc_accent_red",orange:"dialogs.sc_accent_orange"},Ht=null;function Hd(e,t){let o=String(e||"").trim().toLowerCase(),i=Ms();if(Ht&&Ht.queryKey===o&&Ht.styleFilter===t&&Ht.loaded===i)return{items:Ht.items,totalMatches:Ht.totalMatches};let a=Ls(e,120,t);return Ht={queryKey:o,styleFilter:t,loaded:i,items:a.items,totalMatches:a.totalMatches},a}function cn(e,t,o,i,a){if(e.key!=="ArrowLeft"&&e.key!=="ArrowRight"&&e.key!=="ArrowUp"&&e.key!=="ArrowDown"&&e.key!=="Home"&&e.key!=="End")return;e.preventDefault();let n=Math.max(0,t.indexOf(o)),s=n;e.key==="Home"?s=0:e.key==="End"?s=t.length-1:e.key==="ArrowLeft"||e.key==="ArrowUp"?s=(n-1+t.length)%t.length:s=(n+1)%t.length;let r=t[s];if(r===void 0)return;i(r);let c=e.currentTarget.parentElement,u=`#${a}${r||"default"}`;requestAnimationFrame(()=>{c?.querySelector(u)?.focus()})}function Ud(e){let o=(e.startsWith("mdi:")?e.slice(4):e).replace(/[-_]+/g," ").trim();return o?`${o.charAt(0).toUpperCase()+o.slice(1)} (${e})`:e}function Cl(e){let t=e.shortcutModal,o=()=>e.entity.closeShortcutModal(),i=I=>{I.target===I.currentTarget&&o()};if(!t.open)return l`<dialog
      id="latter-shortcut-modal"
      aria-labelledby="latter-shortcut-title"
      @cancel=${o}
      @click=${i}
      class="studio-dialog shortcut-dialog"
    >
      ${v}
    </dialog>`;let a=t.listKey==="dock_items",n=t.editIndex!==null?a?e.t("dialogs.sc_edit_dock"):e.t("dialogs.sc_edit_pinned"):a?e.t("dialogs.sc_add_dock"):e.t("dialogs.sc_add_pinned"),s=e.state?.capabilities,r=Be.filter(I=>!a&&I.dockOnly||a&&(I.token==="settings:root"||Ue.includes(I.token))?!1:me(I,s)),c=[];for(let I of r){let q=I.group||"Apps",X=c.find(ae=>ae.group===q);X?X.items.push(I):c.push({group:q,items:[I]})}let u=e.state?.catalog?.shortcut_entities||[],p=Array.from(new Set(u.map(I=>I.domain))).sort(),m=u.filter(I=>t.entityDomainFilter==="all"||I.domain===t.entityDomainFilter).map(I=>{let q=xo(e.hass,I.id);return{id:I.id,name:I.name,domain:I.domain,area_name:I.area_name,icon:I.icon,state_label:q||void 0}}),g=u.find(I=>I.id===t.entityTarget)||null,_=g?g.domain:t.entityTarget.split(".",1)[0]||"",h=Xe[_]||[],b=r.some(I=>I.token===t.routeTarget)?t.routeTarget:r[0]?.token||t.routeTarget,y=r.find(I=>I.token===b)||Be.find(I=>I.token===b),f=t.kind==="route"?y?.label||e.t("dialogs.sc_default_shortcut"):g?.name||t.entityTarget||e.t("dialogs.sc_default_entity_action"),k=t.kind==="route"?nt[b]||"mdi:apps":g?.icon||"mdi:flash",w=st(t.icon),M=st(t.iconSearch),E=w||(Ro(M)?M:k),N=t.iconSearch.trim().length>0,{items:$,totalMatches:P}=Hd(t.iconSearch,t.iconStyleFilter),H=A(7447,e.hass,0),C=Bt(t.badgeStyle,t.accent),L=$l.map(I=>I.value),D=ti.map(I=>I.token),z=t.badgeStyle==="inverted"?"inverted":"glass",Z=oi.map(I=>I.token),_e=t.accent||"default",Q=I=>{e.shortcutModal={...e.shortcutModal,iconStyleFilter:I},e.host.requestUpdate()},ee=I=>{let q=I==="inverted"?"inverted":"";e.shortcutModal={...e.shortcutModal,badgeStyle:q},e.host.requestUpdate()},oe=I=>{let q=I==="default"?"":I;e.shortcutModal={...e.shortcutModal,accent:q},e.host.requestUpdate()},O=(I,q)=>{e.shortcutModal={...e.shortcutModal,kind:I},e.host.requestUpdate(),q&&requestAnimationFrame(()=>{q.focus()})},re=I=>{if(I.key!=="ArrowLeft"&&I.key!=="ArrowRight"&&I.key!=="Home"&&I.key!=="End")return;I.preventDefault();let q;I.key==="Home"?q="route":I.key==="End"?q="entity":q=t.kind==="route"?"entity":"route";let ae=I.currentTarget.parentElement?.querySelector(q==="route"?"#shortcut-tab-route":"#shortcut-tab-entity");O(q,ae)},K=t.kind==="route";return l`<dialog
    id="latter-shortcut-modal"
    aria-labelledby="latter-shortcut-title"
    @cancel=${o}
    @click=${i}
    class="studio-dialog shortcut-dialog"
  >
    <div class="dialog-body">
      <h3 id="latter-shortcut-title" class="dialog-title">${n}</h3>

      <div role="tablist" aria-label=${e.t("dialogs.sc_type_aria")} class="scope-tabs">
        <button
          type="button"
          id="shortcut-tab-route"
          role="tab"
          aria-selected=${K?"true":"false"}
          aria-controls="shortcut-tabpanel"
          tabindex=${K?"0":"-1"}
          @click=${()=>O("route")}
          @keydown=${re}
          class="scope-tab ${K?"active":""}"
        >
          ${a?e.t("dialogs.sc_tab_subpage"):e.t("dialogs.sc_tab_app_page")}
        </button>
        <button
          type="button"
          id="shortcut-tab-entity"
          role="tab"
          aria-selected=${K?"false":"true"}
          aria-controls="shortcut-tabpanel"
          tabindex=${K?"-1":"0"}
          @click=${()=>O("entity")}
          @keydown=${re}
          class="scope-tab ${K?"":"active"}"
        >
          ${e.t("dialogs.sc_tab_entity")}
        </button>
      </div>

      <div
        id="shortcut-tabpanel"
        role="tabpanel"
        aria-labelledby=${K?"shortcut-tab-route":"shortcut-tab-entity"}
        class="stack"
      >
        ${K?l`<div class="stacked-field">
              <label for="shortcut-route-select">
                ${a?e.t("dialogs.sc_target_subpage"):e.t("dialogs.sc_target_app_page")}
              </label>
              <select
                id="shortcut-route-select"
                .value=${S(b)}
                @change=${I=>{let q=I.currentTarget.value;e.shortcutModal={...e.shortcutModal,routeTarget:q},e.host.requestUpdate()}}
              >
                ${c.map(I=>l`<optgroup label=${I.group}>
                    ${I.items.map(q=>l`<option
                        value=${q.token}
                        .selected=${S(q.token===b)}
                      >
                        ${q.label}
                      </option>`)}
                  </optgroup>`)}
              </select>
            </div>`:l`<div class="stacked-field">
                <label for="shortcut-domain-filter">
                  ${e.t("dialogs.sc_domain_filter")}
                </label>
                <select
                  id="shortcut-domain-filter"
                  .value=${S(t.entityDomainFilter)}
                  @change=${I=>{let q=I.currentTarget.value,X=u.filter(ve=>q==="all"||ve.domain===q),ae=X.some(ve=>ve.id===t.entityTarget)?t.entityTarget:X[0]?.id||"",he=ae.split(".",1)[0]||q,ke=Xe[he]?.[0]?.action||"";e.shortcutModal={...e.shortcutModal,entityDomainFilter:q,entityTarget:ae,action:ke},e.host.requestUpdate()}}
                >
                  <option value="all" .selected=${S(t.entityDomainFilter==="all")}>
                    ${e.t("dialogs.sc_all_domains")}
                  </option>
                  ${p.map(I=>l`<option
                      value=${I}
                      .selected=${S(I===t.entityDomainFilter)}
                    >
                      ${Ps[I]||I}
                    </option>`)}
                </select>
              </div>
              <div class="stacked-field">
                <label for="shortcut-entity-select">
                  ${e.t("dialogs.shortcut_entity_label")}
                </label>
                ${ys({id:"shortcut-entity-select",value:t.entityTarget,options:m,ariaLabel:e.t("dialogs.shortcut_entity_label"),placeholder:e.t("combobox.placeholder"),allowClear:!1,host:e.host,overlay:e.localeOverlay,onChange:I=>{let q=I.split(".",1)[0]||"",X=Xe[q]||[],ae=X.some(he=>he.action===t.action)?t.action:X[0]?.action||"";e.shortcutModal={...e.shortcutModal,entityTarget:I,action:ae},e.host.requestUpdate()}})}
              </div>
              <div class="stacked-field">
                <label for="shortcut-action-select">
                  ${e.t("dialogs.sc_action_label")}
                </label>
                <select
                  id="shortcut-action-select"
                  .value=${S(t.action)}
                  @change=${I=>{e.shortcutModal={...e.shortcutModal,action:I.currentTarget.value},e.host.requestUpdate()}}
                >
                  ${h.map(I=>l`<option
                      value=${I.action}
                      .selected=${S(I.action===t.action)}
                    >
                      ${I.label}
                    </option>`)}
                </select>
              </div>
              ${j({id:"shortcut-confirm-switch",label:e.t("dialogs.sc_confirm_label"),description:a?e.t("dialogs.sc_confirm_dock_desc"):e.t("dialogs.sc_confirm_pinned_desc"),checked:t.confirm,onChange:I=>{e.shortcutModal={...e.shortcutModal,confirm:I},e.host.requestUpdate()}})}`}
      </div>

      <div class="stacked-field">
        <label for="shortcut-label-input">${e.t("dialogs.sc_custom_label")}</label>
        <input
          type="text"
          id="shortcut-label-input"
          maxlength=${String(wo)}
          placeholder=${f}
          .value=${V(t.label)}
          @input=${I=>{e.shortcutModal={...e.shortcutModal,label:I.currentTarget.value}}}
        />
      </div>

      <div class="stacked-field">
        <label for="shortcut-icon-input">${e.t("dialogs.sc_icon_label")}</label>
        <div class="shortcut-icon-row">
          <span id="shortcut-icon-preview" class=${C} aria-hidden="true">
            <ha-icon .icon=${E}></ha-icon>
          </span>
          <input
            type="text"
            id="shortcut-icon-input"
            placeholder=${e.t("dialogs.sc_icon_search_placeholder",{total:H})}
            .value=${V(t.iconSearch)}
            @input=${I=>{let q=I.currentTarget.value;e.shortcutModal={...e.shortcutModal,iconSearch:q},e.host.requestUpdate()}}
          />
          ${t.icon||t.iconSearch?l`<button
                type="button"
                @click=${()=>{e.shortcutModal={...e.shortcutModal,icon:"",iconSearch:""},e.host.requestUpdate()}}
                class="btn btn-text btn-compact"
              >
                ${e.t("action.default_icon")}
              </button>`:v}
        </div>
        <div class="shortcut-picker-bar">
          <p class="row-description shortcut-picker-status">
            ${w?e.t("dialogs.sc_icon_selected",{icon:w}):e.t("dialogs.sc_icon_default",{icon:k})}
            •
            ${N?P===0?e.t("dialogs.sc_icon_no_matches"):P>$.length?e.t("dialogs.sc_icon_showing_subset",{shown:A($.length,e.hass,0),total:A(P,e.hass,0)}):P===1?e.t("dialogs.sc_icon_matches_one"):e.t("dialogs.sc_icon_matches_many",{count:A(P,e.hass,0)}):t.iconStyleFilter==="all"?e.t("dialogs.sc_icon_popular",{total:H}):e.t("dialogs.sc_icon_popular_filtered",{style:t.iconStyleFilter==="solid"?e.t("dialogs.sc_icon_style_solid").toLowerCase():e.t("dialogs.sc_icon_style_outline").toLowerCase(),total:A(P,e.hass,0)})}
          </p>
          <div
            id="shortcut-icon-style-filter"
            role="radiogroup"
            aria-label=${e.t("dialogs.sc_icon_style_aria")}
            class="segmented shortcut-style-filter"
          >
            ${$l.map(I=>{let q=t.iconStyleFilter===I.value;return l`<button
                type="button"
                id=${`shortcut-icon-style-${I.value}`}
                role="radio"
                aria-checked=${q?"true":"false"}
                tabindex=${q?"0":"-1"}
                @click=${()=>Q(I.value)}
                @keydown=${X=>cn(X,L,t.iconStyleFilter,Q,"shortcut-icon-style-")}
              >
                ${e.t(I.labelKey)}
              </button>`})}
          </div>
        </div>
        <div
          role="group"
          aria-label=${e.t("dialogs.sc_mdi_group_aria")}
          class="mdi-picker-grid"
        >
          ${$.map(I=>{let q=w===I;return l`<button
              type="button"
              title=${I}
              aria-label=${Ud(I)}
              aria-pressed=${q?"true":"false"}
              @click=${()=>{e.shortcutModal={...e.shortcutModal,icon:I},e.host.requestUpdate()}}
              class="mdi-picker-btn ${q?"selected":""}"
            >
              <ha-icon .icon=${I}></ha-icon>
            </button>`})}
        </div>
      </div>

      <div class="stacked-field">
        <span id="shortcut-badge-style-label" class="field-label">
          ${e.t("dialogs.sc_badge_style_label")}
        </span>
        <div
          id="shortcut-badge-style-group"
          role="radiogroup"
          aria-labelledby="shortcut-badge-style-label"
          class="segmented shortcut-badge-style"
        >
          ${ti.map(I=>{let q=z===I.token,X=Bd[I.token];return l`<button
              type="button"
              id=${`shortcut-badge-style-${I.token}`}
              role="radio"
              aria-checked=${q?"true":"false"}
              tabindex=${q?"0":"-1"}
              @click=${()=>ee(I.token)}
              @keydown=${ae=>cn(ae,D,z,ee,"shortcut-badge-style-")}
            >
              ${X?e.t(X):I.label}
            </button>`})}
        </div>
      </div>

      <div class="stacked-field">
        <span id="shortcut-accent-label" class="field-label">
          ${e.t("dialogs.sc_accent_label")}
        </span>
        <div
          id="shortcut-accent-group"
          role="radiogroup"
          aria-labelledby="shortcut-accent-label"
          class="shortcut-accent-pills"
        >
          ${oi.map(I=>{let q=_e===I.token,X=Nd[I.token];return l`<button
              type="button"
              id=${`shortcut-accent-${I.token}`}
              role="radio"
              aria-checked=${q?"true":"false"}
              tabindex=${q?"0":"-1"}
              @click=${()=>oe(I.token)}
              @keydown=${ae=>cn(ae,Z,_e,oe,"shortcut-accent-")}
              class="accent-pill-btn"
            >
              <span
                class=${`accent-swatch-dot swatch-${I.token}`}
                aria-hidden="true"
              ></span>
              <span>${X?e.t(X):I.label}</span>
            </button>`})}
        </div>
      </div>

      <div class="dialog-actions">
        <button type="button" @click=${o} class="btn btn-secondary">
          ${e.t("action.cancel")}
        </button>
        <button
          type="button"
          id="shortcut-save-btn"
          @click=${()=>e.entity.saveShortcutModal()}
          class="btn btn-primary"
        >
          ${e.t("action.save_shortcut")}
        </button>
      </div>
    </div>
  </dialog>`}function Tl(e,t){let o=[["latter-rm-modal",t.removeModal.open],["latter-reset-modal",t.resetModal.open],["latter-add-dev-modal",t.addBleModal.open],["latter-cw-modal",t.colorWheelModal.open],["latter-save-group-modal",t.saveGroupModal.open],["latter-app-config-modal",t.appConfigModal.open],["latter-camera-config-modal",t.cameraConfigModal.open],["latter-shortcut-modal",t.shortcutModal.open],["latter-photo-upload-modal",t.photoUploadModal.open],["latter-photo-edit-modal",t.photoEditModal.open],["latter-media-import-modal",t.mediaImportModal.open],["latter-photo-picker-modal",t.photoPickerModal.open]];for(let[i,a]of o){if(a)continue;let n=e.getElementById(i);n&&n.open&&typeof n.close=="function"&&n.close()}for(let[i,a]of o){if(!a)continue;let n=e.getElementById(i);n&&!n.open&&typeof n.showModal=="function"&&n.showModal()}ul(e,t),fl(e,t)}function xl(e){return l`
    ${ml(e)}
    ${gl(e)}
    ${_l(e)}
    ${pl(e)}
    ${hl(e)}
    ${sl(e)}
    ${cl(e)}
    ${Cl(e)}
    ${Sl(e)}
    ${kl(e)}
    ${vl(e)}
    ${bl(e)}
  `}var Al=xe`
  .card {
    min-inline-size: 0;
    container-type: inline-size;
    background: var(--studio-surface);
    border: var(--studio-card-border-width) solid var(--studio-card-border);
    border-radius: var(--studio-radius-card);
    box-shadow: var(--studio-card-shadow);
    color: var(--studio-text);
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .card.danger { border-color: var(--studio-error); }
  .card.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-card-handoff-shadow);
    background: var(--studio-handoff-surface);
  }
  .handoff-active[tabindex="-1"]:focus-visible { outline: none; }
  .card-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding-block: var(--studio-space-card-top) 0;
    padding-inline: var(--studio-space-4);
  }
  .card-heading {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    min-inline-size: 0;
    flex: 1 1 240px;
  }
  .card-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    letter-spacing: var(--studio-card-title-tracking);
    line-height: var(--studio-line-height-condensed);
  }
  .card-subtitle, .row-description, .help-text {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .card-header-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .card-content {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-4);
  }
  .card-actions {
    display: flex;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  details.card > summary {
    list-style: none;
    cursor: pointer;
    padding-block-end: var(--studio-space-card-top);
  }
  details.card > summary::-webkit-details-marker { display: none; }
  details.card > summary::after {
    content: "▾";
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.card[open] > summary::after { transform: rotate(180deg); }
  details.card[open] > summary { border-block-end: 1px solid var(--studio-divider); }
  details.sub-collapsible {
    border-block-start: 1px solid var(--studio-divider);
    padding-block-start: var(--studio-space-3);
  }
  details.sub-collapsible > summary {
    cursor: pointer;
    font-weight: var(--studio-weight-medium);
  }
  details.sub-collapsible > .card-content {
    padding-block: var(--studio-space-3) 0;
    padding-inline: 0;
  }
  details.sub-collapsible.summary-row > summary {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    list-style: none;
  }
  details.sub-collapsible.summary-row > summary::-webkit-details-marker { display: none; }
  .summary-row-end {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .summary-chevron {
    color: var(--studio-text-secondary);
    transition: transform 0.15s ease;
  }
  details.sub-collapsible.summary-row[open] > summary .summary-chevron {
    transform: rotate(180deg);
  }
  .hub-domain-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .hub-domain-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height-compact);
  }
  .hub-domain-title {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-weight: var(--studio-weight-medium);
  }
  .hub-domain-title svg {
    width: 18px;
    height: 18px;
    fill: var(--studio-primary);
    flex-shrink: 0;
  }
  .hub-domain-empty {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .hub-slot-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  .hub-slot-row > select {
    flex: 1 1 200px;
    min-inline-size: 0;
    max-inline-size: 100%;
  }
  .hub-slot-meta {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
  }
  .area-presence-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .area-presence-box.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
    background: var(--studio-primary-tint);
  }
  .area-box-head {
    display: flex;
    align-items: safe center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-heading {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-title {
    flex: 1 1 140px;
    min-inline-size: 0;
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .area-box-actions {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-inline-start: auto;
  }
  .area-box-badges {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .area-box-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > .settings-row {
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-2) 0;
    padding-inline: 0;
    border-block-start: 1px solid var(--studio-divider);
  }
  .area-presence-box > details.sub-collapsible {
    padding-block-start: var(--studio-space-2);
  }
  .area-presence-box > details.sub-collapsible > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .area-presence-box > details.sub-collapsible[open] > summary,
  .area-presence-box > details.sub-collapsible > summary:hover {
    color: var(--studio-text);
  }
  .subsection-title {
    padding-block-start: var(--studio-space-3);
    border-block-start: 1px solid var(--studio-divider);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
  }
  .card-content > .subsection-title:first-child { padding-block-start: 0; border-block-start: none; }
  .lux-bounds-row {
    display: flex;
    align-items: safe center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .lux-bound-field {
    display: inline-flex;
    align-items: safe center;
    gap: var(--studio-space-1);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .lux-number-input {
    inline-size: 76px;
    min-block-size: var(--studio-control-height-compact);
    padding-block: var(--studio-space-1);
    padding-inline: var(--studio-space-2);
  }
`;var El=xe`
  .settings-list {
    display: flex;
    flex-direction: column;
  }
  .settings-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--studio-space-4);
    min-height: var(--studio-row-min-height);
    padding-block: var(--studio-space-2);
    padding-inline: 0;
  }
  .settings-row-text {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .row-label { font-weight: var(--studio-weight-regular); }
  .row-description { line-height: normal; }
  .settings-row-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .settings-row-control select,
  .settings-row-control .combobox,
  .settings-row-control input[type="text"],
  .settings-row-control input[type="search"],
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] {
    inline-size: 260px;
    max-inline-size: 100%;
  }
  .settings-row-control input[type="number"],
  .settings-row-control input[type="time"],
  .settings-row-control input[type="password"] { inline-size: 140px; }
  .settings-row.stacked { grid-template-columns: minmax(0, 1fr); }
  .settings-row.stacked .settings-row-control { justify-content: stretch; }
  .settings-row.stacked .settings-row-control > * { flex: 1 1 200px; inline-size: auto; }

  select,
  input[type="text"],
  input[type="search"],
  input[type="number"],
  input[type="time"],
  input[type="password"],
  textarea {
    min-height: var(--studio-control-height);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-block-end: 1px solid var(--studio-field-line);
    border-radius: var(--studio-radius-field) var(--studio-radius-field) 0 0;
    background: var(--studio-field-bg);
    color: var(--studio-text);
    color-scheme: inherit;
    font: inherit;
    transition: background-color 0.15s ease-out;
  }
  textarea {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    resize: vertical;
  }
  select:hover,
  input[type="text"]:hover,
  input[type="search"]:hover,
  input[type="number"]:hover,
  input[type="time"]:hover,
  input[type="password"]:hover,
  textarea:hover {
    background: var(--studio-field-bg-hover);
  }
  select option, select optgroup {
    background-color: var(--studio-popup-bg);
    color: var(--studio-text);
  }
  input::placeholder, textarea::placeholder {
    color: var(--studio-text-secondary);
    opacity: 1;
  }
  input[readonly] { color: var(--studio-text-secondary); }
  input[type="file"] { color: var(--studio-text-secondary); font: inherit; }
  input[type="range"] { inline-size: 140px; accent-color: var(--studio-primary); }

  select:focus-visible,
  input:focus-visible,
  textarea:focus-visible,
  button:focus-visible,
  a:focus-visible,
  summary:focus-visible,
  [tabindex]:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  select:focus-visible,
  input[type="text"]:focus-visible,
  input[type="search"]:focus-visible,
  input[type="number"]:focus-visible,
  input[type="time"]:focus-visible,
  input[type="password"]:focus-visible,
  textarea:focus-visible {
    outline: none;
    border-block-end-color: var(--studio-primary);
    box-shadow: inset 0 -1px 0 var(--studio-primary);
  }

  /* RTL-safe toggle switch */
  .switch {
    appearance: none;
    position: relative;
    inline-size: 48px;
    block-size: 24px;
    margin: 0;
    border: 1px solid var(--studio-switch-border);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-switch-track);
    cursor: pointer;
    flex-shrink: 0;
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }
  .switch::after {
    content: "";
    position: absolute;
    inset-block-start: 2px;
    inset-inline-start: 2px;
    inline-size: 18px;
    block-size: 18px;
    border-radius: 50%;
    background: var(--studio-switch-thumb);
    box-shadow: var(--studio-switch-thumb-shadow);
    transition: transform 0.15s ease, background-color 0.15s ease;
  }
  .switch:checked {
    background: var(--studio-switch-on-track);
    border-color: var(--studio-switch-on-border);
  }
  .switch:checked::after {
    transform: translateX(24px);
    background: var(--studio-switch-on-thumb);
  }
  :host(:dir(rtl)) .switch:checked::after {
    transform: translateX(-24px);
  }
  .switch:disabled { opacity: 0.3; cursor: not-allowed; }

  .input-action-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .input-action-row > input:not([type="file"]),
  .input-action-row > select,
  .input-action-row > .combobox {
    flex: 1 1 180px;
    min-inline-size: 0;
  }
  .input-action-row > input[type="file"] { flex: 0 1 auto; max-inline-size: 100%; }

  .segmented {
    display: inline-flex;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
  }
  .segmented button {
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .segmented button[aria-checked="true"] {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .inline-switch {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
    cursor: pointer;
    white-space: nowrap;
  }
  .list-row {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-main {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: var(--studio-space-2);
    flex: 1;
    min-inline-size: 0;
  }
  .list-row-grow { flex: 1; min-inline-size: 0; }
  .list-block {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .list-row-head {
    display: flex;
    align-items: flex-end;
    gap: var(--studio-space-2);
  }
  .stacked-field {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .stacked-field > label, .stacked-field > .field-label {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .stacked-field > select,
  .stacked-field > input,
  .stacked-field > .combobox { inline-size: 100%; }
  .stack {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }

  /* Buttons */
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height);
    padding-block: 0;
    padding-inline: var(--studio-space-4);
    border: none;
    border-radius: var(--studio-radius-button);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    line-height: 1;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
    transition: background-color 0.15s ease-out;
  }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-compact {
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
  }
  .btn-primary { background: var(--studio-btn-accent-bg); color: var(--studio-btn-accent-text); }
  .btn-primary:hover:not(:disabled) { background: var(--studio-btn-accent-bg-hover); }
  .btn-secondary { background: var(--studio-btn-tonal-bg); color: var(--studio-btn-tonal-text); }
  .btn-secondary:hover:not(:disabled) { background: var(--studio-btn-tonal-bg-hover); }
  .btn-text {
    background: transparent;
    color: var(--studio-btn-tonal-text);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
  }
  .btn-text:hover:not(:disabled) { background: var(--studio-btn-plain-hover); }
  .btn-danger { background: var(--studio-danger-tonal-bg); color: var(--studio-danger-tonal-text); }
  .btn-danger:hover:not(:disabled) { filter: brightness(0.95); }
  .btn-danger-filled { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .btn-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height);
    block-size: var(--studio-control-height);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .btn-icon:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-icon:hover:not(:disabled) { background: var(--studio-hover); }
  .btn-icon.danger { color: var(--studio-error); }
  .btn-icon svg { inline-size: 20px; block-size: 20px; fill: currentColor; }

  .quick-action-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
    padding-block-end: var(--studio-space-3);
    border-block-end: 1px solid var(--studio-divider);
  }
  .quick-action-grid:last-child {
    padding-block-end: 0;
    border-block-end: none;
  }
  .quick-action-btn {
    justify-content: flex-start;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border-radius: var(--studio-radius-control);
    white-space: normal;
    text-align: start;
    line-height: var(--studio-line-height-condensed);
  }
  .quick-action-btn svg {
    inline-size: 18px;
    block-size: 18px;
    fill: currentColor;
    flex-shrink: 0;
  }

  /* WAI-ARIA 1.2 searchable entity combobox */
  .combobox {
    position: relative;
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
  }
  .combobox-input-wrap {
    position: relative;
    display: flex;
    align-items: center;
    inline-size: 100%;
  }
  .combobox-input-wrap > input[role="combobox"] {
    inline-size: 100%;
    padding-inline-end: calc(var(--studio-control-height-compact) + var(--studio-space-2));
  }
  .combobox-clear {
    position: absolute;
    inset-inline-end: var(--studio-space-1);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height-compact);
    block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: 50%;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    cursor: pointer;
  }
  .combobox-clear:hover {
    background: var(--studio-hover);
    color: var(--studio-text);
  }
  .combobox-listbox {
    position: absolute;
    inset-block-start: calc(100% + var(--studio-space-1));
    inset-inline: 0;
    z-index: 45;
    max-height: 280px;
    margin: 0;
    padding: var(--studio-space-1);
    list-style: none;
    overflow-y: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-popup-bg);
    box-shadow: var(--studio-overlay-shadow);
  }
  .combobox-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-1);
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-field);
    cursor: pointer;
  }
  .combobox-option:hover,
  .combobox-option.active {
    background: var(--studio-hover);
  }
  .combobox-option[aria-selected="true"] {
    background: var(--studio-nav-active-bg);
    color: var(--studio-nav-active-text);
  }
  .combobox-option-main {
    display: flex;
    flex-direction: column;
    min-inline-size: 0;
    flex: 1;
  }
  .combobox-option-title {
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .combobox-option-id {
    color: var(--studio-text-secondary);
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-caption);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .combobox-option-chips {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    flex-shrink: 0;
  }
  .combobox-empty,
  .combobox-footer {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
  }
  .combobox-footer {
    border-block-start: 1px solid var(--studio-divider);
  }

  /* Pointer drag-and-drop & keyboard sortable rows */
  .sortable-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
  }
  .sortable-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    transition: border-color 0.12s ease, opacity 0.12s ease, background-color 0.12s ease;
  }
  .sortable-row.dragging,
  .pill.dragging {
    opacity: 0.65;
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
  }
  .sortable-row.drag-over-before {
    border-block-start: 2px solid var(--studio-primary);
  }
  .sortable-row.drag-over-after {
    border-block-end: 2px solid var(--studio-primary);
  }
  .pill.drag-over-before {
    box-shadow: inset 2px 0 0 var(--studio-primary);
  }
  .pill.drag-over-after {
    box-shadow: inset -2px 0 0 var(--studio-primary);
  }
  :host(:dir(rtl)) .pill.drag-over-before {
    box-shadow: inset -2px 0 0 var(--studio-primary);
  }
  :host(:dir(rtl)) .pill.drag-over-after {
    box-shadow: inset 2px 0 0 var(--studio-primary);
  }
  .drag-handle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-field);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    line-height: 1;
    cursor: grab;
    touch-action: none;
    user-select: none;
    flex-shrink: 0;
  }
  .drag-handle:hover {
    background: var(--studio-hover);
    color: var(--studio-text);
  }
  .drag-handle:active {
    cursor: grabbing;
  }
  .sortable-row-content {
    flex: 1;
    min-inline-size: 0;
  }
  .sortable-row-actions {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    max-inline-size: 100%;
  }
  .sortable-row-stacked {
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-3);
  }
  .sortable-row-head {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    inline-size: 100%;
  }
  .sortable-row-title {
    flex: 1 1 auto;
    min-inline-size: 0;
  }
  .sortable-row-stacked > .sortable-row-content {
    inline-size: 100%;
  }

  @container (max-width: 520px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-block-start: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select,
    .settings-row-control .combobox,
    .settings-row-control input[type="text"],
    .settings-row-control input[type="search"],
    .settings-row-control input[type="password"] {
      inline-size: 100%;
    }
  }
  @container (max-width: 360px) {
    .quick-action-grid { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 860px) {
    .settings-row { grid-template-columns: minmax(0, 1fr); }
    .settings-row + .settings-row { border-block-start: 1px solid var(--studio-divider); }
    .settings-row-control { justify-content: flex-start; }
    .settings-row-control select,
    .settings-row-control .combobox,
    .settings-row-control input[type="text"],
    .settings-row-control input[type="search"],
    .settings-row-control input[type="password"] {
      inline-size: 100%;
    }
  }
  @media (max-width: 480px) {
    .list-row { flex-wrap: wrap; }
    .list-row-head { flex-wrap: wrap; }
    .list-row-main { grid-template-columns: minmax(0, 1fr); inline-size: 100%; }
  }
`;var Il=xe`
  .kv-list { display: flex; flex-direction: column; gap: 0; }
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    min-height: var(--studio-control-height);
    padding-block: var(--studio-space-1);
    padding-inline: 0;
  }
  .kv-row > span:first-child { color: var(--studio-text-secondary); }
  .kv-row > strong, .kv-value {
    font-weight: var(--studio-weight-medium);
    font-variant-numeric: tabular-nums;
    text-align: end;
  }
  button.kv-row {
    inline-size: 100%;
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: start;
    cursor: pointer;
  }
  button.kv-row:hover { background: var(--studio-hover); }
  button.kv-row > strong::after {
    content: " ›";
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  :host(:dir(rtl)) button.kv-row > strong::after {
    content: " ‹";
  }

  .table-wrap {
    inline-size: 100%;
    overflow-x: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  table.data-table {
    inline-size: 100%;
    border-collapse: collapse;
    text-align: start;
  }
  table.data-table th {
    padding: 0;
    border-block-end: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  .sort-btn {
    inline-size: 100%;
    padding: var(--studio-space-3);
    border: none;
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: start;
    cursor: pointer;
  }
  .sort-btn:hover { color: var(--studio-text); }
  th[aria-sort="ascending"] .sort-btn,
  th[aria-sort="descending"] .sort-btn {
    color: var(--studio-primary);
  }
  table.data-table td {
    padding: var(--studio-space-3);
    border-block-end: 1px solid var(--studio-divider);
    white-space: nowrap;
  }
  table.data-table tbody tr:last-child td { border-block-end: none; }
  table.data-table tbody tr { cursor: pointer; }
  table.data-table tbody tr:hover,
  table.data-table tbody tr:focus-within,
  table.data-table tbody tr:focus-visible {
    background: var(--studio-hover);
  }
  td.col-name { font-weight: var(--studio-weight-medium); }
  table.data-table a { color: inherit; text-decoration: none; border-radius: var(--studio-radius-field); }
  table.data-table a:hover { text-decoration: underline; }
  table.data-table a:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
    text-decoration: underline;
  }
  td.col-open { color: var(--studio-text-secondary); text-align: end; }

  /* WCAG 2.2 AA >= 4.5:1 semantic chips */
  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: 22px;
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .chip-primary {
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .chip-success {
    background: var(--studio-chip-success-bg);
    color: var(--studio-chip-success-text);
  }
  .chip-warning {
    background: var(--studio-chip-warning-bg);
    color: var(--studio-chip-warning-text);
  }
  .chip-error {
    background: var(--studio-chip-danger-bg);
    color: var(--studio-chip-danger-text);
  }
  .status-dot {
    display: inline-block;
    inline-size: 8px;
    block-size: 8px;
    margin-inline-end: var(--studio-space-2);
    border-radius: 50%;
    background: var(--studio-text-disabled);
  }
  .chip > .status-dot { margin-inline-end: var(--studio-space-1); }
  .status-dot.online { background: var(--studio-success); }
  .status-dot.update { background: var(--studio-warning); }

  .status-tiles {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-2);
  }
  @container (max-width: 260px) {
    .status-tiles { grid-template-columns: minmax(0, 1fr); }
  }
  .status-tile {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-1);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: start;
  }
  button.status-tile {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.status-tile:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  button.status-tile:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .status-tile-head {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile-head svg {
    inline-size: 16px;
    block-size: 16px;
    fill: currentColor;
    flex-shrink: 0;
  }
  .status-tile-value {
    margin-block-start: var(--studio-space-1);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .status-tile-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }
  .status-tile > .signal-track { margin-block-start: var(--studio-space-1); }
  @container (max-width: 420px) {
    .status-tile {
      gap: 0;
      padding-block: var(--studio-space-2);
      padding-inline: var(--studio-space-3);
    }
    .status-tile-head { gap: var(--studio-space-1); }
    .status-tile-value {
      margin-block-start: var(--studio-space-1);
      font-size:var(--studio-font-body);
    }
    .status-tile-meta {
      margin-block-start: var(--studio-space-1);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }

  .overview-box {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: var(--studio-space-2);
    inline-size: 100%;
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    text-align: start;
  }
  button.overview-box {
    cursor: pointer;
    transition: background-color 0.15s ease-out, border-color 0.15s ease-out;
  }
  button.overview-box:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  .overview-box-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .overview-box-title {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .overview-box-title svg {
    inline-size: 18px;
    block-size: 18px;
    fill: currentColor;
    color: var(--studio-text-secondary);
    flex-shrink: 0;
  }
  .overview-box-end {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .overview-box-chevron {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .overview-box-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    line-height: var(--studio-line-height-condensed);
  }

  /* >= 32px WCAG 2.2 AA pill targets & sortable pills */
  .pill-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .pill {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
  }
  .pill.enabled {
    border-color: var(--studio-primary);
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .pill-move {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-move:hover:not(:disabled) {
    background: var(--studio-hover);
    color: var(--studio-primary);
  }
  .pill-move:disabled { opacity: 0.4; cursor: not-allowed; }
  .pill-toggle {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: var(--studio-control-height-compact);
    min-block-size: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
  }
  .pill-toggle:disabled { opacity: 0.5; cursor: not-allowed; }
  .pill .drag-handle {
    border-radius: var(--studio-radius-pill);
    color: inherit;
  }

  .swatch {
    display: inline-block;
    inline-size: 20px;
    block-size: 20px;
    border-radius: 50%;
    border: 1px solid var(--studio-divider);
    background: var(--swatch-color, var(--studio-primary));
    flex-shrink: 0;
  }

  /* BLE rows & upload progress */
  #card-ble-calibration {
    scroll-margin-top: calc(var(--studio-header-height) + var(--studio-space-4));
  }
  .calibrate-target-box {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    transition: border-color 0.2s ease, background-color 0.2s ease, box-shadow 0.2s ease;
  }
  .calibrate-target-box.handoff-active {
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
    background: var(--studio-primary-tint);
  }
  .calibrate-handoff-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-weight: var(--studio-weight-medium);
  }
  .signal-row {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .signal-row.winner { border-color: var(--studio-primary); }
  .proxy-trim-details { padding-block-start: var(--studio-space-2); }
  .proxy-trim-details > summary {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }
  .proxy-trim-details[open] > summary,
  .proxy-trim-details > summary:hover {
    color: var(--studio-text);
  }
  .proxy-trim-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
  }
  .signal-row-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-row-title {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .signal-meta { color: var(--studio-text-secondary); font-size:var(--studio-font-secondary); }
  .signal-track, .upload-progress {
    block-size: 6px;
    border-radius: var(--studio-radius-pill);
    background: var(--studio-surface-alt);
    overflow: hidden;
  }
  .signal-fill {
    inline-size: var(--signal-pct, 0%);
    block-size: 100%;
    background: var(--studio-primary);
    transition: inline-size 0.25s ease, width 0.25s ease;
  }
  .signal-fill.low { background: var(--studio-error); }
  .upload-progress-fill {
    inline-size: var(--upload-pct, 0%);
    block-size: 100%;
    background: var(--studio-primary);
    transition: inline-size 0.15s ease, width 0.15s ease;
  }

  /* Photo Library, Collection Filter Strip, Bulk Toolbar & Compact Pool Previews (D-072) */
  .photo-upload-status {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
  }
  .photo-toolbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .photo-toolbar-start,
  .photo-toolbar-end {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .photo-search-input {
    min-inline-size: 200px;
    flex: 1 1 220px;
  }
  .collection-strip {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .collection-chip-wrap {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-1);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
  }
  .collection-chip-wrap.active {
    border-color: var(--studio-primary);
    background: var(--studio-chip-primary-bg);
    color: var(--studio-chip-primary-text);
  }
  .collection-chip-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    font: inherit;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .collection-chip-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-inline-size: 28px;
    min-block-size: 28px;
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-pill);
    background: transparent;
    color: inherit;
    cursor: pointer;
  }
  .collection-chip-action:hover {
    background: var(--studio-hover);
  }
  .collection-chip-action svg {
    inline-size: 14px;
    block-size: 14px;
    fill: currentColor;
  }
  .photo-bulk-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-primary);
    border-radius: var(--studio-radius-control);
    background: var(--studio-primary-tint);
  }
  .photo-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(168px, 1fr));
    gap: var(--studio-space-3);
  }
  .photo-grid > .empty-state {
    grid-column: 1 / -1;
  }
  .photo-tile {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    content-visibility: auto;
    contain-intrinsic-size: 180px 220px;
    transition: border-color 0.15s ease, background-color 0.15s ease, box-shadow 0.15s ease;
  }
  .photo-tile:hover {
    border-color: var(--studio-primary);
  }
  .photo-tile.selected {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    box-shadow: var(--studio-photo-ring-selected);
  }
  .photo-tile-thumb-btn {
    position: relative;
    display: block;
    inline-size: 100%;
    padding: 0;
    border: none;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
    overflow: hidden;
    cursor: pointer;
    aspect-ratio: 1 / 1;
    line-height: 0;
  }
  .photo-tile-thumb-btn.circle {
    border-radius: 50%;
  }
  .photo-tile-thumb-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .photo-tile-img {
    inline-size: 100%;
    block-size: 100%;
    object-fit: cover;
    display: block;
  }
  .photo-tile-check {
    position: absolute;
    inset-block-start: var(--studio-space-2);
    inset-inline-start: var(--studio-space-2);
    z-index: 2;
    inline-size: 20px;
    block-size: 20px;
    accent-color: var(--studio-primary);
    cursor: pointer;
  }
  .photo-tile-badge {
    position: absolute;
    inset-block-end: var(--studio-space-1);
    inset-inline-end: var(--studio-space-1);
    padding-block: 2px;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-photo-badge-bg);
    color: var(--studio-photo-badge-text);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    line-height: var(--studio-line-height-condensed);
  }
  .photo-tile-meta {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .photo-tile-name {
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .photo-tile-sub {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
  }
  .photo-pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    padding-block-start: var(--studio-space-2);
    border-block-start: 1px solid var(--studio-divider);
  }
  .photo-pool-preview {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .photo-pool-thumbs {
    display: flex;
    align-items: center;
    gap: var(--studio-space-1);
    flex-shrink: 0;
  }
  .photo-pool-thumb {
    inline-size: 48px;
    block-size: 48px;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
  }
  .photo-pool-thumb.circle {
    border-radius: 50%;
  }
  .photo-pool-info {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1 1 160px;
  }
  .photo-pool-title {
    font-weight: var(--studio-weight-medium);
    overflow-wrap: break-word;
  }
  .photo-pool-meta {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
    overflow-wrap: break-word;
  }
  .photo-pool-actions {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    min-inline-size: 0;
    max-inline-size: 100%;
  }
  .cam-preview {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .cam-preview img {
    inline-size: 100%;
    max-inline-size: 360px;
    aspect-ratio: 16 / 9;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    background: var(--studio-media-bg);
  }
  .log-output {
    max-block-size: 380px;
    margin: 0;
    padding: var(--studio-space-3);
    overflow: auto;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    white-space: pre-wrap;
  }

  /* Empty, loading, alerts, toast, & shadow-safe offscreen helpers */
  .empty-state {
    padding-block: var(--studio-space-3);
    padding-inline: 0;
    color: var(--studio-text-secondary);
  }
  .loading-state {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    padding-block: var(--studio-space-5);
    padding-inline: 0;
    color: var(--studio-text-secondary);
  }
  .loading-state::before {
    content: "";
    inline-size: 20px;
    block-size: 20px;
    border: 2px solid var(--studio-divider);
    border-block-start-color: var(--studio-primary);
    border-radius: 50%;
    animation: studio-spin 0.8s linear infinite;
  }
  .studio-root:not(.is-loading) #studio-loading { display: none; }
  @keyframes studio-spin { to { transform: rotate(360deg); } }

  .alert {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-info-tint);
  }
  .alert-error { background: var(--studio-error-tint); }
  .alert-warning { background: var(--studio-warning-tint); }
  .alert-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
  }
  .alert-list {
    margin: 0;
    padding-inline-start: var(--studio-space-5);
  }
  .toast {
    position: fixed;
    inset-inline: 0;
    inset-block-end: var(--studio-space-5);
    margin-inline: auto;
    inline-size: fit-content;
    z-index: 50;
    max-inline-size: min(560px, calc(100vw - 32px));
    padding-block: var(--studio-space-3);
    padding-inline: var(--studio-space-4);
    border-radius: var(--studio-radius-field);
    background: var(--studio-toast-bg);
    color: var(--studio-toast-text);
    box-shadow: var(--studio-overlay-shadow);
  }
  .toast.error { background: var(--studio-danger-loud-bg); color: var(--studio-danger-loud-text); }
  .offscreen,
  .sr-only {
    position: fixed;
    inset-block-start: 0;
    inset-inline-start: 0;
    inline-size: 1px;
    block-size: 1px;
    padding: 0;
    margin: 0;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: none;
    opacity: 0;
    pointer-events: none;
  }
`;var Pl=xe`
  dialog.studio-dialog {
    inline-size: min(460px, calc(100vw - 32px));
    max-block-size: calc(100vh - 32px);
    max-block-size: calc(100dvh - 32px);
    padding: var(--studio-space-5);
    border: none;
    border-radius: var(--studio-radius-dialog);
    background: var(--studio-surface);
    color: var(--studio-text);
    box-shadow: var(--studio-overlay-shadow);
    overflow-y: auto;
    overscroll-behavior: contain;
  }
  dialog.studio-dialog::backdrop { background: var(--studio-scrim); }
  dialog.studio-dialog.confirm-dialog {
    inline-size: min(480px, calc(100vw - 32px));
  }
  .dialog-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .dialog-header-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .dialog-title {
    font-size:var(--studio-font-card-title);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height-condensed);
  }
  .dialog-text { color: var(--studio-text-secondary); }
  .dialog-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-block-start: var(--studio-space-2);
  }
  .dialog-actions.with-secondary {
    justify-content: space-between;
  }
  .dialog-actions-end {
    display: inline-flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    margin-inline-start: auto;
  }

  dialog.studio-dialog.shortcut-dialog {
    inline-size: min(560px, calc(100vw - 32px));
  }
  dialog.studio-dialog.photo-dialog {
    inline-size: min(680px, calc(100vw - 32px));
  }
  .crop-dropzone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-5);
    border: 2px dashed var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    text-align: center;
    cursor: pointer;
    transition: border-color 0.15s ease, background-color 0.15s ease;
  }
  .crop-dropzone.dragging,
  .crop-dropzone:hover {
    border-color: var(--studio-primary);
    background: var(--studio-dropzone-bg);
  }
  .crop-stage-wrap {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface-alt);
  }
  .crop-canvas {
    max-inline-size: 100%;
    block-size: auto;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
    cursor: grab;
    touch-action: none;
    display: block;
  }
  .crop-canvas.dragging {
    cursor: grabbing;
  }
  .crop-canvas.round {
    border-radius: 50%;
  }
  .crop-controls-row {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    inline-size: 100%;
  }
  .crop-zoom-control {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    flex: 1 1 200px;
  }
  .crop-zoom-control input[type="range"] {
    flex: 1;
    min-inline-size: 120px;
  }
  .crop-filmstrip {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    overflow-x: auto;
    overscroll-behavior-inline: contain;
    padding-block: var(--studio-space-1);
    inline-size: 100%;
  }
  .crop-filmstrip-item {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    border: 2px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    cursor: pointer;
    flex-shrink: 0;
  }
  .crop-filmstrip-item.active {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
  }
  .crop-filmstrip-btn {
    padding: 0;
    border: none;
    background: transparent;
    border-radius: var(--studio-radius-control);
    cursor: pointer;
    line-height: 0;
  }
  .crop-filmstrip-btn:focus-visible {
    outline: 2px solid var(--studio-primary);
    outline-offset: 2px;
  }
  .crop-filmstrip-thumb {
    inline-size: 56px;
    block-size: 56px;
    object-fit: cover;
    border-radius: var(--studio-radius-field);
    background: var(--studio-media-bg);
    display: block;
  }
  .crop-filmstrip-remove {
    position: absolute;
    inset-block-start: -6px;
    inset-inline-end: -6px;
    inline-size: 24px;
    block-size: 24px;
    border-radius: var(--studio-radius-pill);
    border: 1px solid var(--studio-divider);
    background: var(--studio-surface);
    color: var(--studio-text);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    padding: 0;
    font-size:var(--studio-font-caption);
  }
  .crop-filmstrip-remove:hover {
    background: var(--studio-danger-tonal-bg);
    color: var(--studio-danger-tonal-text);
    border-color: var(--studio-error);
  }
  .media-breadcrumbs {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
    padding-block: var(--studio-space-1);
  }
  .media-folder-list {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: var(--studio-space-2);
  }
  .media-folder-btn {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: var(--studio-text);
    font: inherit;
    text-align: start;
    cursor: pointer;
    min-inline-size: 0;
  }
  .media-folder-btn:hover {
    border-color: var(--studio-primary);
    background: var(--studio-hover);
  }
  .media-folder-btn span {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .media-scroll-area {
    max-block-size: 360px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-1);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-3);
  }
  .photo-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
    gap: var(--studio-space-2);
    max-block-size: 320px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-1);
  }
  .photo-picker-item {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--studio-space-1);
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: center;
  }
  .photo-picker-item:hover {
    border-color: var(--studio-primary);
  }
  .photo-picker-item.selected {
    border-color: var(--studio-primary);
    background: var(--studio-primary-tint);
    box-shadow: var(--studio-photo-ring-selected);
  }
  .photo-picker-thumb {
    inline-size: 88px;
    block-size: 88px;
    object-fit: cover;
    border-radius: var(--studio-radius-control);
    border: 1px solid var(--studio-divider);
    background: var(--studio-media-bg);
  }
  .photo-picker-thumb.circle {
    border-radius: 50%;
  }
  .photo-picker-name {
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    inline-size: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-item-row,
  .dock-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .dock-row {
    flex-wrap: wrap;
  }
  .dock-row .shortcut-item-info {
    flex: 1 1 180px;
  }
  .dock-row .shortcut-item-title,
  .dock-row .shortcut-item-meta {
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .shortcut-item-row.shortcut-item-locked,
  .dock-row.shortcut-item-locked {
    border-style: dashed;
    background: transparent;
  }
  .shortcut-item-row.shortcut-item-locked .shortcut-icon-badge,
  .shortcut-item-row.shortcut-item-hidden .shortcut-icon-badge,
  .dock-row.shortcut-item-locked .shortcut-icon-badge,
  .dock-row.shortcut-item-hidden .shortcut-icon-badge {
    background: var(--studio-surface-alt);
    color: var(--studio-text-secondary);
  }
  .shortcut-icon-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    inline-size: var(--studio-control-height-compact);
    block-size: var(--studio-control-height-compact);
    border-radius: var(--studio-radius-pill);
    border: 1px solid var(--studio-badge-glass-border);
    background: var(--studio-badge-glass-bg);
    color: var(--studio-badge-glass-fg);
    flex-shrink: 0;
    transition: background-color 0.15s ease, color 0.15s ease, border-color 0.15s ease;
  }
  .shortcut-icon-badge.accent-primary {
    background: var(--studio-badge-glass-primary-bg);
    color: var(--studio-badge-glass-primary-fg);
    border-color: var(--studio-badge-glass-primary-border);
  }
  .shortcut-icon-badge.accent-gold {
    background: var(--studio-badge-glass-gold-bg);
    color: var(--studio-badge-glass-gold-fg);
    border-color: var(--studio-badge-glass-gold-border);
  }
  .shortcut-icon-badge.accent-green {
    background: var(--studio-badge-glass-green-bg);
    color: var(--studio-badge-glass-green-fg);
    border-color: var(--studio-badge-glass-green-border);
  }
  .shortcut-icon-badge.accent-red {
    background: var(--studio-badge-glass-red-bg);
    color: var(--studio-badge-glass-red-fg);
    border-color: var(--studio-badge-glass-red-border);
  }
  .shortcut-icon-badge.accent-orange {
    background: var(--studio-badge-glass-orange-bg);
    color: var(--studio-badge-glass-orange-fg);
    border-color: var(--studio-badge-glass-orange-border);
  }
  .shortcut-icon-badge.badge-inverted {
    background: var(--studio-badge-inv-bg);
    color: var(--studio-badge-inv-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-primary {
    background: var(--studio-badge-inv-primary-bg);
    color: var(--studio-badge-inv-primary-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-gold {
    background: var(--studio-badge-inv-gold-bg);
    color: var(--studio-badge-inv-gold-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-green {
    background: var(--studio-badge-inv-green-bg);
    color: var(--studio-badge-inv-green-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-red {
    background: var(--studio-badge-inv-red-bg);
    color: var(--studio-badge-inv-red-fg);
    border-color: transparent;
  }
  .shortcut-icon-badge.badge-inverted.accent-orange {
    background: var(--studio-badge-inv-orange-bg);
    color: var(--studio-badge-inv-orange-fg);
    border-color: transparent;
  }
  .shortcut-picker-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .shortcut-picker-status {
    flex: 1 1 200px;
    min-inline-size: 0;
  }
  .shortcut-style-filter {
    flex-shrink: 0;
  }
  .shortcut-badge-style {
    align-self: flex-start;
  }
  .shortcut-accent-pills {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-1);
  }
  .accent-pill-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--studio-space-1);
    min-height: var(--studio-control-height-compact);
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text);
    font: inherit;
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
    transition: background-color 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }
  .accent-pill-btn:hover {
    background: var(--studio-hover);
    border-color: var(--studio-primary);
  }
  .accent-pill-btn[aria-checked="true"] {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
    border-color: var(--studio-primary);
    box-shadow: var(--studio-handoff-ring);
  }
  .accent-swatch-dot {
    inline-size: var(--studio-swatch-dot-size);
    block-size: var(--studio-swatch-dot-size);
    border-radius: var(--studio-radius-pill);
    border: 1px solid transparent;
    flex-shrink: 0;
  }
  .accent-swatch-dot.swatch-default {
    background: var(--studio-badge-glass-bg);
    border-color: var(--studio-text-secondary);
  }
  .accent-swatch-dot.swatch-primary {
    background: var(--studio-accent-dot-primary);
  }
  .accent-swatch-dot.swatch-gold {
    background: var(--studio-accent-dot-gold);
  }
  .accent-swatch-dot.swatch-green {
    background: var(--studio-accent-dot-green);
  }
  .accent-swatch-dot.swatch-red {
    background: var(--studio-accent-dot-red);
  }
  .accent-swatch-dot.swatch-orange {
    background: var(--studio-accent-dot-orange);
  }
  .shortcut-item-info {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1;
  }
  .shortcut-item-title {
    font-weight: var(--studio-weight-medium);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-item-meta {
    font-size:var(--studio-font-secondary);
    color: var(--studio-text-secondary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .shortcut-page-group {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding: var(--studio-space-3);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface-alt);
  }
  .shortcut-page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-size:var(--studio-font-secondary);
    font-weight: var(--studio-weight-medium);
    color: var(--studio-text-secondary);
  }
  .shortcut-toolbar {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }
  .shortcut-icon-row input[type="text"] {
    flex: 1;
    min-inline-size: 0;
  }
  .mdi-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(40px, 1fr));
    gap: var(--studio-space-1);
    max-block-size: 168px;
    overflow-y: auto;
    overscroll-behavior: contain;
    padding: var(--studio-space-2);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: var(--studio-input-bg);
  }
  .mdi-picker-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    block-size: var(--studio-control-height);
    border: 1px solid transparent;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    cursor: pointer;
  }
  .mdi-picker-btn:hover { background: var(--studio-hover); }
  .mdi-picker-btn.selected {
    background: var(--studio-chip-primary-bg);
    border-color: var(--studio-primary);
    color: var(--studio-chip-primary-text);
  }
  .color-wheel { display: flex; justify-content: center; }
  .color-wheel canvas { border-radius: 50%; cursor: crosshair; touch-action: none; }
  .color-hex-row {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--studio-space-2);
  }
  .color-hex-row input[type="text"] {
    inline-size: 120px;
    font-family: var(--studio-font-code);
    text-align: center;
  }
  .color-hex-row input[type="color"] {
    inline-size: var(--studio-control-height);
    block-size: var(--studio-control-height);
    padding: 0;
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
    background: none;
    cursor: pointer;
  }
`;var Ml=xe`
  header.latter-top-titlebar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-3);
    height: var(--studio-header-height);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    background: var(--studio-header-bg);
    color: var(--studio-header-text);
    border-block-end: var(--studio-header-border);
    position: sticky;
    inset-block-start: 0;
    z-index: 30;
  }
  .titlebar-brand {
    display: flex;
    align-items: center;
    gap: var(--studio-space-3);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
    user-select: none;
  }
  .titlebar-brand .ha-menu-btn { color: var(--studio-header-icon); display: none; }
  :host([show-menu]) .titlebar-brand .ha-menu-btn { display: inline-flex; }
  .titlebar-title { padding-inline-start: var(--studio-space-3); }
  :host([show-menu]) .titlebar-title { padding-inline-start: 0; }
  .titlebar-actions {
    display: flex;
    align-items: center;
    gap: var(--studio-space-2);
  }

  .app-shell {
    display: grid;
    grid-template-columns: var(--studio-sidebar-width) minmax(0, 1fr);
    min-height: calc(100vh - var(--studio-header-height));
    min-height: calc(100dvh - var(--studio-header-height));
  }
  aside.sidebar {
    min-inline-size: 0;
    background: var(--studio-sidebar-bg);
    border-inline-end: 1px solid var(--studio-divider);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-2);
    padding-block: var(--studio-space-4);
    padding-inline: var(--studio-space-3);
    position: sticky;
    inset-block-start: var(--studio-header-height);
    height: calc(100vh - var(--studio-header-height));
    height: calc(100dvh - var(--studio-header-height));
    overflow-y: auto;
  }
  .scope-tabs {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--studio-space-1);
    padding: var(--studio-space-1);
    background: var(--studio-input-bg);
    border: 1px solid var(--studio-divider);
    border-radius: var(--studio-radius-control);
  }
  .scope-tab {
    min-height: var(--studio-control-height-compact);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text-secondary);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    cursor: pointer;
  }
  .scope-tab.active {
    background: var(--studio-btn-tonal-bg);
    color: var(--studio-btn-tonal-text);
  }
  .nav-list {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
  }
  .nav-btn {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--studio-space-2);
    width: 100%;
    min-height: var(--studio-control-height);
    padding-block: 0;
    padding-inline: var(--studio-space-3);
    border: none;
    border-radius: var(--studio-radius-control);
    background: transparent;
    color: var(--studio-text);
    font: inherit;
    font-weight: var(--studio-weight-medium);
    text-align: start;
    text-decoration: none;
    white-space: nowrap;
    cursor: pointer;
  }
  .nav-btn:hover { background: var(--studio-hover); }
  .nav-btn.active {
    background: var(--studio-nav-active-bg);
    color: var(--studio-nav-active-text);
  }
  .nav-btn.nav-back-btn { color: var(--studio-text-secondary); }
  .nav-device-title {
    padding-block: var(--studio-space-2);
    padding-inline: var(--studio-space-3);
    border-block-start: 1px solid var(--studio-divider);
    border-block-end: 1px solid var(--studio-divider);
    font-size:var(--studio-font-section);
    font-weight: var(--studio-weight-medium);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-inline-start: var(--studio-space-4); }
  .nav-badge {
    min-inline-size: 20px;
    padding-block: 0;
    padding-inline: var(--studio-space-2);
    border-radius: var(--studio-radius-pill);
    background: var(--studio-input-bg);
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-caption);
    font-weight: var(--studio-weight-medium);
    text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .main-area { min-inline-size: 0; }
  .content-wrap {
    max-inline-size: 1140px;
    margin-block: 0;
    margin-inline: auto;
    padding: var(--studio-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    container-type: inline-size;
    container-name: studio-content;
  }
  .content-wrap > section {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    min-inline-size: 0;
  }
  .page-title {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: var(--studio-space-2);
    font-size:var(--studio-font-title);
    font-weight: var(--studio-weight-regular);
  }
  .page-subtitle {
    color: var(--studio-text-secondary);
    font-weight: var(--studio-weight-regular);
  }
  .is-loading .content-wrap > section { display: none !important; }
  .columns {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--studio-space-4);
    align-items: start;
  }
  .column {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-4);
    min-inline-size: 0;
  }
  @container studio-content (max-width: 760px) {
    .columns { grid-template-columns: minmax(0, 1fr); }
  }
  @media (max-width: 860px) {
    .titlebar-brand .ha-menu-btn { display: inline-flex; }
    .titlebar-title { padding-inline-start: 0; }
    .app-shell { grid-template-columns: minmax(0, 1fr); grid-template-rows: auto 1fr; }
    aside.sidebar {
      align-self: start;
      position: sticky;
      inset-block-start: var(--studio-header-height);
      z-index: 25;
      block-size: auto;
      padding-block: var(--studio-space-2);
      padding-inline: var(--studio-space-3);
      border-inline-end: none;
      border-block-end: 1px solid var(--studio-divider);
    }
    .nav-device-title { display: none; }
    .nav-list {
      flex-direction: row;
      overflow-x: auto;
      scrollbar-width: none;
      padding-inline: var(--studio-space-1);
      -webkit-mask-image: var(--studio-nav-scroll-mask);
      mask-image: var(--studio-nav-scroll-mask);
    }
    .nav-list::-webkit-scrollbar { display: none; }
    .nav-btn {
      inline-size: auto;
      border: 1px solid var(--studio-divider);
      border-radius: var(--studio-radius-pill);
    }
    #nav-scope-device .nav-btn:not(.nav-back-btn) { padding-inline-start: var(--studio-space-3); }
    .content-wrap {
      padding-block: var(--studio-space-4) var(--studio-space-5);
      padding-inline: var(--studio-space-3);
    }
  }
`;var Fd=xe`
  :host {
    /* Typography & spacing scale */
    --studio-font-family: var(--ha-font-family-body, inherit);
    --studio-font-code: var(--ha-font-family-code, monospace);
    --studio-font-title: var(--ha-font-size-xl, 20px);
    --studio-font-section: var(--ha-font-size-l, 16px);
    --studio-font-body: var(--ha-font-size-m, 14px);
    --studio-font-secondary: var(--ha-font-size-s, 12px);
    --studio-font-caption: var(--ha-font-size-s, 12px);
    --studio-weight-regular: var(--ha-font-weight-normal, 400);
    --studio-weight-medium: var(--ha-font-weight-medium, 500);
    --studio-line-height: var(--ha-line-height-normal, 1.6);
    --studio-line-height-condensed: var(--ha-line-height-condensed, 1.2);
    --studio-font-card-title: var(--ha-card-header-font-size, var(--ha-font-size-2xl, 24px));
    --studio-card-title-tracking: -0.012em;
    --studio-space-1: var(--ha-space-1, 4px);
    --studio-space-2: var(--ha-space-2, 8px);
    --studio-space-3: var(--ha-space-3, 12px);
    --studio-space-4: var(--ha-space-4, 16px);
    --studio-space-card-top: var(--ha-space-5, 20px);
    --studio-space-5: var(--ha-space-6, 24px);

    /* Radii & geometry */
    --studio-radius-card: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    --studio-radius-control: var(--ha-border-radius-md, 8px);
    --studio-radius-field: var(--ha-border-radius-sm, 4px);
    --studio-radius-button: var(--ha-button-border-radius, var(--ha-border-radius-pill, 9999px));
    --studio-radius-dialog: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    --studio-radius-pill: var(--ha-border-radius-pill, 9999px);
    --studio-card-border-width: var(--ha-card-border-width, 1px);
    --studio-control-height: var(--ha-button-height, 40px);
    --studio-control-height-compact: 32px;
    --studio-row-min-height: 56px;
    --studio-header-height: var(--header-height, 56px);
    --studio-sidebar-width: 244px;

    /* Surfaces & borders */
    --studio-bg: var(--primary-background-color, #fafafa);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #ffffff));
    --studio-surface-alt: var(--secondary-background-color, #f0f0f0);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #ffffff));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #212121));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #616161));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #ffffff));
    --studio-input-bg: var(--input-fill-color, rgba(0, 0, 0, 0.04));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #f5f5f5));
    --studio-field-bg-hover: var(--ha-color-form-background-hover, var(--studio-field-bg));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(0, 0, 0, 0.42)));
    --studio-popup-bg: var(--card-background-color, #ffffff);
    --studio-divider: var(--divider-color, rgba(0, 0, 0, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    --studio-text: var(--primary-text-color, #212121);
    --studio-text-secondary: var(--secondary-text-color, #5f6368);
    --studio-text-disabled: var(--disabled-text-color, #9e9e9e);
    --studio-primary: var(--primary-color, #007299);
    --studio-primary-tint: rgba(var(--rgb-primary-color, 0, 154, 199), 0.12);
    --studio-hover: rgba(var(--rgb-primary-text-color, 33, 33, 33), 0.06);

    /* WCAG 2.2 AA (>= 4.5:1) tonal fill/text pairs for buttons, active nav, & semantic chips */
    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, var(--primary-color, #007da3));
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, var(--studio-btn-accent-bg));
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, var(--text-primary-color, #ffffff));
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, #c2e6f2);
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, #005b78);
    --studio-btn-plain-hover: var(--ha-color-fill-primary-quiet-resting, var(--studio-primary-tint));
    --studio-nav-active-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-nav-active-text: var(--ha-color-on-primary-normal, #005b78);

    --studio-chip-primary-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-chip-primary-text: var(--ha-color-on-primary-normal, #005b78);
    --studio-chip-success-bg: var(--ha-color-fill-success-normal-resting, #dcf2df);
    --studio-chip-success-text: var(--ha-color-on-success-normal, #1b5e20);
    --studio-chip-warning-bg: var(--ha-color-fill-warning-normal-resting, #fff0d1);
    --studio-chip-warning-text: var(--ha-color-on-warning-normal, #7a4900);
    --studio-chip-danger-bg: var(--ha-color-fill-danger-normal-resting, #fbe4e2);
    --studio-chip-danger-text: var(--ha-color-on-danger-normal, #9e1c13);

    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, #fbe4e2);
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, #9e1c13);
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, #c62828);
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);

    /* Per-shortcut badge style & semantic accent tokens (WCAG 2.2 AA >= 4.5:1) */
    --studio-swatch-dot-size: 12px;
    --studio-badge-glass-bg: #e8ecf0;
    --studio-badge-glass-fg: #212121;
    --studio-badge-glass-border: rgba(0, 0, 0, 0.14);
    --studio-badge-glass-primary-bg: var(--ha-color-fill-primary-normal-resting, #d8eff7);
    --studio-badge-glass-primary-fg: var(--ha-color-on-primary-normal, #005b78);
    --studio-badge-glass-primary-border: rgba(0, 114, 153, 0.28);
    --studio-badge-glass-gold-bg: #fef3c7;
    --studio-badge-glass-gold-fg: #78350f;
    --studio-badge-glass-gold-border: rgba(217, 119, 6, 0.32);
    --studio-badge-glass-green-bg: #dcfce7;
    --studio-badge-glass-green-fg: #14532d;
    --studio-badge-glass-green-border: rgba(22, 163, 74, 0.3);
    --studio-badge-glass-red-bg: #fee2e2;
    --studio-badge-glass-red-fg: #991b1b;
    --studio-badge-glass-red-border: rgba(220, 38, 38, 0.3);
    --studio-badge-glass-orange-bg: #ffedd5;
    --studio-badge-glass-orange-fg: #9a3412;
    --studio-badge-glass-orange-border: rgba(234, 88, 12, 0.32);

    --studio-badge-inv-bg: #1f2937;
    --studio-badge-inv-fg: #ffffff;
    --studio-badge-inv-primary-bg: var(--ha-color-fill-primary-loud-resting, #007299);
    --studio-badge-inv-primary-fg: var(--ha-color-on-primary-loud, #ffffff);
    --studio-badge-inv-gold-bg: #f59e0b;
    --studio-badge-inv-gold-fg: #1c1917;
    --studio-badge-inv-green-bg: #15803d;
    --studio-badge-inv-green-fg: #ffffff;
    --studio-badge-inv-red-bg: #c62828;
    --studio-badge-inv-red-fg: #ffffff;
    --studio-badge-inv-orange-bg: #c2410c;
    --studio-badge-inv-orange-fg: #ffffff;

    --studio-accent-dot-primary: var(--primary-color, #007299);
    --studio-accent-dot-gold: #d97706;
    --studio-accent-dot-green: #16a34a;
    --studio-accent-dot-red: #dc2626;
    --studio-accent-dot-orange: #ea580c;

    /* Switch, status, shadows, & scroll masks */
    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #e0e0e0));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #616161));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, #d8eff7));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, #005b78));
    --studio-switch-thumb-shadow: var(--ha-switch-thumb-box-shadow, var(--ha-box-shadow-s, 0 1px 2px rgba(0, 0, 0, 0.3)));
    --studio-toast-bg: var(--primary-text-color, #212121);
    --studio-toast-text: var(--card-background-color, #ffffff);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(140, 140, 140));
    --studio-success: var(--success-color, #2e7d32);
    --studio-warning: var(--warning-color, #ef6c00);
    --studio-error: var(--error-color, #c62828);
    --studio-info: var(--info-color, #0277bd);
    --studio-warning-tint: color-mix(in srgb, var(--studio-warning) 14%, transparent);
    --studio-error-tint: color-mix(in srgb, var(--studio-error) 14%, transparent);
    --studio-info-tint: color-mix(in srgb, var(--studio-info) 14%, transparent);
    --studio-card-shadow: var(--ha-card-box-shadow, none);
    --studio-handoff-surface: color-mix(in srgb, var(--studio-primary) 8%, var(--studio-surface));
    --studio-handoff-ring: inset 0 0 0 1px var(--studio-primary);
    --studio-card-handoff-shadow: inset 0 0 0 1px var(--studio-primary), var(--studio-card-shadow);
    --studio-overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    --studio-scrim: rgba(0, 0, 0, 0.5);
    --studio-media-bg: var(--secondary-background-color, #000000);
    --studio-photo-badge-bg: rgba(0, 0, 0, 0.68);
    --studio-photo-badge-text: #ffffff;
    --studio-photo-ring-selected: 0 0 0 2px var(--studio-primary);
    --studio-dropzone-bg: color-mix(in srgb, var(--studio-primary) 6%, var(--studio-input-bg));
    --studio-nav-scroll-mask: linear-gradient(
      to right,
      transparent 0,
      #000000 12px,
      #000000 calc(100% - 16px),
      transparent 100%
    );

    display: block;
    min-height: 100vh;
    min-height: 100dvh;
    background: var(--studio-bg);
    color: var(--studio-text);
    font-family: var(--studio-font-family);
    font-size:var(--studio-font-body);
    font-weight: var(--studio-weight-regular);
    line-height: var(--studio-line-height);
    -webkit-tap-highlight-color: transparent;
    color-scheme: light;
    scrollbar-color: var(--studio-scrollbar-thumb) transparent;
    scrollbar-width: thin;
  }

  :host([dark]) {
    --studio-bg: var(--primary-background-color, #111111);
    --studio-surface: var(--ha-card-background, var(--card-background-color, #1c1c1c));
    --studio-surface-alt: var(--secondary-background-color, #282828);
    --studio-header-bg: var(--app-header-background-color, var(--sidebar-background-color, #1c1c1c));
    --studio-header-text: var(--app-header-text-color, var(--primary-text-color, #e1e1e1));
    --studio-header-icon: var(--sidebar-icon-color, var(--secondary-text-color, #9b9b9b));
    --studio-header-border: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-sidebar-bg: var(--sidebar-background-color, var(--card-background-color, #1c1c1c));
    --studio-input-bg: var(--input-fill-color, rgba(255, 255, 255, 0.05));
    --studio-field-bg: var(--ha-color-form-background, var(--input-fill-color, #363636));
    --studio-field-line: var(--ha-color-border-neutral-loud, var(--input-idle-line-color, rgba(255, 255, 255, 0.42)));
    --studio-popup-bg: var(--card-background-color, #1c1c1c);
    --studio-divider: var(--divider-color, rgba(225, 225, 225, 0.12));
    --studio-card-border: var(--ha-card-border-color, var(--divider-color, rgba(225, 225, 225, 0.12)));
    --studio-text: var(--primary-text-color, #e1e1e1);
    --studio-text-secondary: var(--secondary-text-color, #a8a8a8);
    --studio-text-disabled: var(--disabled-text-color, #6f6f6f);
    --studio-primary: var(--primary-color, #38bdf8);
    --studio-hover: rgba(var(--rgb-primary-text-color, 225, 225, 225), 0.06);

    --studio-btn-accent-bg: var(--ha-color-fill-primary-loud-resting, #006a8e);
    --studio-btn-accent-bg-hover: var(--ha-color-fill-primary-loud-hover, #007da3);
    --studio-btn-accent-text: var(--ha-color-on-primary-loud, #ffffff);
    --studio-btn-tonal-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-btn-tonal-bg-hover: var(--ha-color-fill-primary-normal-hover, #104559);
    --studio-btn-tonal-text: var(--ha-color-on-primary-normal, #7bd6f5);
    --studio-nav-active-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-nav-active-text: var(--ha-color-on-primary-normal, #7bd6f5);

    --studio-chip-primary-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-chip-primary-text: var(--ha-color-on-primary-normal, #7bd6f5);
    --studio-chip-success-bg: var(--ha-color-fill-success-normal-resting, #143619);
    --studio-chip-success-text: var(--ha-color-on-success-normal, #81e287);
    --studio-chip-warning-bg: var(--ha-color-fill-warning-normal-resting, #3b2a07);
    --studio-chip-warning-text: var(--ha-color-on-warning-normal, #ffd166);
    --studio-chip-danger-bg: var(--ha-color-fill-danger-normal-resting, #3d1614);
    --studio-chip-danger-text: var(--ha-color-on-danger-normal, #ff9b93);

    --studio-danger-tonal-bg: var(--ha-color-fill-danger-normal-resting, #3d1614);
    --studio-danger-tonal-text: var(--ha-color-on-danger-normal, #ff9b93);
    --studio-danger-loud-bg: var(--ha-color-fill-danger-loud-resting, #c62828);
    --studio-danger-loud-text: var(--ha-color-on-danger-loud, #ffffff);

    --studio-badge-glass-bg: #2c3138;
    --studio-badge-glass-fg: #f1f5f9;
    --studio-badge-glass-border: rgba(255, 255, 255, 0.16);
    --studio-badge-glass-primary-bg: var(--ha-color-fill-primary-normal-resting, #0b3545);
    --studio-badge-glass-primary-fg: var(--ha-color-on-primary-normal, #7bd6f5);
    --studio-badge-glass-primary-border: rgba(56, 189, 248, 0.34);
    --studio-badge-glass-gold-bg: #3d2b08;
    --studio-badge-glass-gold-fg: #fcd34d;
    --studio-badge-glass-gold-border: rgba(251, 191, 36, 0.34);
    --studio-badge-glass-green-bg: #10331e;
    --studio-badge-glass-green-fg: #6ee7b7;
    --studio-badge-glass-green-border: rgba(74, 222, 128, 0.32);
    --studio-badge-glass-red-bg: #3f1515;
    --studio-badge-glass-red-fg: #fca5a5;
    --studio-badge-glass-red-border: rgba(248, 113, 113, 0.34);
    --studio-badge-glass-orange-bg: #411e09;
    --studio-badge-glass-orange-fg: #fdba74;
    --studio-badge-glass-orange-border: rgba(251, 146, 60, 0.34);

    --studio-badge-inv-bg: #f1f5f9;
    --studio-badge-inv-fg: #111827;
    --studio-badge-inv-primary-bg: #38bdf8;
    --studio-badge-inv-primary-fg: #082f49;
    --studio-badge-inv-gold-bg: #fbbf24;
    --studio-badge-inv-gold-fg: #1c1917;
    --studio-badge-inv-green-bg: #4ade80;
    --studio-badge-inv-green-fg: #052e16;
    --studio-badge-inv-red-bg: #f87171;
    --studio-badge-inv-red-fg: #450a0a;
    --studio-badge-inv-orange-bg: #fb923c;
    --studio-badge-inv-orange-fg: #431407;

    --studio-accent-dot-primary: var(--primary-color, #38bdf8);
    --studio-accent-dot-gold: #fbbf24;
    --studio-accent-dot-green: #4ade80;
    --studio-accent-dot-red: #f87171;
    --studio-accent-dot-orange: #fb923c;

    --studio-switch-track: var(--ha-switch-background-color, var(--ha-color-fill-disabled-quiet-resting, #202020));
    --studio-switch-border: var(--ha-switch-border-color, var(--ha-color-border-neutral-normal, #7a7a7a));
    --studio-switch-thumb: var(--ha-switch-thumb-background-color, var(--ha-color-on-neutral-normal, #989898));
    --studio-switch-on-track: var(--ha-switch-checked-background-color, var(--ha-color-fill-primary-normal-resting, #0b3545));
    --studio-switch-on-border: var(--ha-switch-checked-border-color, var(--ha-color-border-primary-loud, var(--primary-color, #009ac7)));
    --studio-switch-on-thumb: var(--ha-switch-checked-thumb-background-color, var(--ha-color-on-primary-normal, #7bd6f5));
    --studio-toast-bg: var(--primary-text-color, #e1e1e1);
    --studio-toast-text: var(--card-background-color, #1c1c1c);
    --studio-scrollbar-thumb: var(--scrollbar-thumb-color, rgb(110, 110, 110));
    --studio-success: var(--success-color, #43a047);
    --studio-warning: var(--warning-color, #ffa600);
    --studio-error: var(--error-color, #db4437);
    --studio-info: var(--info-color, #039be5);
    color-scheme: dark;
  }

  * { box-sizing: border-box; }
  .hidden { display: none !important; }
  .studio-root {
    min-height: 100vh;
    min-height: 100dvh;
    display: flex;
    flex-direction: column;
    background: var(--studio-bg);
  }
  h2, h3, h4, p { margin: 0; }
  code, .mono {
    font-family: var(--studio-font-code);
    font-size:var(--studio-font-secondary);
  }
  a { color: var(--studio-primary); }

  /* Upgrade & offline / sleeping Device banners */
  .studio-rev-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-2) var(--studio-space-4);
    background: var(--studio-chip-warning-bg);
    border-block-end: 1px solid var(--studio-warning);
    color: var(--studio-chip-warning-text);
    z-index: 40;
  }
  .offline-banner,
  .alert.offline-banner {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: var(--studio-space-3);
    padding: var(--studio-space-3) var(--studio-space-4);
    border: 1px solid var(--studio-divider);
    border-inline-start: 4px solid var(--studio-warning);
    border-radius: var(--studio-radius-control);
    background: var(--studio-surface);
    color: var(--studio-text);
  }
  .offline-banner-body {
    display: flex;
    flex-direction: column;
    gap: var(--studio-space-1);
    min-inline-size: 0;
    flex: 1 1 260px;
  }
  .offline-banner-body > span {
    color: var(--studio-text-secondary);
    font-size:var(--studio-font-secondary);
  }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.01ms !important;
      animation-iteration-count: 1 !important;
      transition-duration: 0.01ms !important;
      scroll-behavior: auto !important;
    }
  }
`;var Dl=xe`
  ${Fd}
  ${Ml}
  ${Al}
  ${El}
  ${Il}
  ${Pl}
`;function Rl(e){let t=e.state,o=t?.config||{},i=t?.capabilities||{},a=t?.live||{},n=e.entity.getPref("wake_word_mode"),s=n?String(n.value)==="Disabled":!1,r=e.entity.getPref("wake_screen_on_assist"),u=e.entity.getSectionItems("voice").filter($=>{if($.domain==="assist_satellite")return!1;let P=$.key||$.pref_key||$.entity_id&&$.entity_id.split(".").pop()||"";return!(P==="va_visual_profile"||P.endsWith("_visual_profile")||P==="wake_word_mode"||P.endsWith("_wake_word_mode")||P==="wake_screen_on_assist"||P.endsWith("_wake_screen_on_assist")||P.startsWith("ww_sens_")||P.includes("_ww_sens_")||s&&($.key==="wake_word"||$.key==="wake_word_n"||P.endsWith("_wake_word")||P.endsWith("_wake_word_n")))}),p=s?[]:e.entity.getPrefs(["ww_sens_okay_nabu","ww_sens_hey_luna","ww_sens_hey_jarvis","ww_sens_hey_mycroft","ww_sens_alexa"]),d=e.entity.getPrefs(["alert_volume","volume_step_size","game_sound_effects"]),m=e.entity.getSectionItems("sound").filter($=>!$.pref_key),g=!!o.native_ble_tracking&&i.is_roaming_device!==!1,_=Number(o.area_follow_dwell_s??10),h=t?.esphome?.device?.node_name||o.device_slug||"",b=h?`media_player.${h}`:"",y=String(o.ma_player_entity||"").trim(),f=a.ma_link_matched===!1,w=f||!!(y&&y!==b),M=b||e.t("dev_audio.ma_player_fallback_target"),E=f?e.t("dev_audio.ma_player_unmatched_desc",{entity:M}):e.t("dev_audio.ma_player_manual_desc",{entity:M}),N=t?.catalog?.ma_speakers;return l`<section id="view-audio_voice">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${U({heading:l`<h3 class="card-title">${e.t("dev_audio.card_voice_wake")}</h3>`,contentClass:"settings-list",body:l`${n?pe(e,n):v}
            ${u.map($=>Ce(e,$))}
            ${r?pe(e,r):v}
            ${g?l`${j({rowId:"row-sync-device-area",id:"cfg-sync_device_area",label:e.tPrefLabel("sync_device_area"),description:e.t("dev_audio.vfm_desc"),checked:!!o.sync_device_area,onChange:$=>e.entity.stageDeviceSetting("sync_device_area",$,"cfg-sync_device_area")})}
                  ${Zt({rowId:"row-area-follow-dwell",id:"cfg-area_follow_dwell_s",label:e.t("dev_audio.vfm_delay_label"),ariaLabel:e.t("dev_audio.vfm_delay_label"),description:e.t("dev_audio.vfm_delay_desc"),value:_,min:3,max:60,step:1,unit:"s",hass:e.hass,onCommit:$=>e.entity.stageDeviceSetting("area_follow_dwell_s",$||10,"cfg-area_follow_dwell_s")})}`:v}
            ${p.length?l`<details class="sub-collapsible">
                  <summary>${e.t("dev_audio.ww_sensitivity_summary")}</summary>
                  <div class="card-content settings-list">
                    ${p.map($=>pe(e,$))}
                  </div>
                </details>`:v}`})}
      </div>

      <div class="column">
        ${U({heading:l`<h3 class="card-title">
            ${e.t("dev_audio.card_sound_playback")}
          </h3>`,contentClass:"settings-list",body:l`${se({id:"cfg-default_speaker",label:e.t("dev_audio.default_speaker_label"),description:e.t("dev_audio.default_speaker_desc"),value:o.default_speaker,choices:N,emptyOptionLabel:e.t("dev_audio.default_speaker_auto"),onChange:$=>e.entity.stageDeviceSetting("default_speaker",$,"cfg-default_speaker")})}
            ${w?se({rowId:"row-ma-player-entity",id:"cfg-ma_player_entity",label:e.t("dev_audio.ma_player_label"),description:E,descId:"desc-ma-player-entity",value:y,choices:t?.catalog?.ma_players,emptyOptionLabel:e.t("dev_audio.ma_player_auto"),onChange:$=>e.entity.stageDeviceSetting("ma_player_entity",$,"cfg-ma_player_entity")}):v}
            ${j({id:"cfg-area_handoff",label:e.tPrefLabel("area_handoff"),description:e.t("dev_audio.area_handoff_desc"),checked:!!o.area_handoff,onChange:$=>e.entity.stageDeviceSetting("area_handoff",$,"cfg-area_handoff")})}
            ${d.map($=>pe(e,$))}
            ${m.map($=>Ce(e,$))}`})}
      </div>
    </div>
  </section>`}function Ll(e,t,o){let i=`dev_display.rot_${t}`,a=e.t(i);return a===i?o:a}function dn(e,t){return e==null?t:typeof e=="string"?!["","0","false","off","disabled"].includes(e.trim().toLowerCase()):!!e}function Ol(e,t,o,i,a,n){if(t==="off"||t==="single"&&!o)return{title:e.t("common.disabled"),meta:e.t("dev_display.pool_off_meta")};if(t==="single"){let c=(a[0]||n.find(u=>u.id===o)||null)?.name||o;return{title:c,meta:e.t("dev_display.pool_single_meta",{name:c})}}if(t==="collection"){let r=Ti(e,i),c=a.length;return{title:r,meta:c===1?e.t("dev_display.pool_collection_one_meta",{collection:r}):e.t("dev_display.pool_collection_meta",{collection:r,count:A(c,e.hass,0)})}}let s=a.length;return{title:s===1?e.t("dev_display.pool_custom_one_meta"):e.t("dev_display.pool_custom_meta",{count:A(s,e.hass,0)}),meta:s>0?a.slice(0,3).map(r=>r.name||r.id).join(", ")+(s>3?"\u2026":""):e.t("dev_display.pool_off_meta")}}function Bl(e){let t=e.state,o=t?.config||{},i=t?.live||{},a=(t?.system_config?.custom_palettes||[]).filter(F=>ue(F.hex)),s=((t?.system_devices||[]).find(F=>F.subentry_id===e.activeSubentryId)||(t?.system_devices||[]).find(F=>F.is_current))?.is_online===!1,r=String(o.display_shape||"square")==="circle"?"circle":"",c=(t?.wallpapers&&t.wallpapers.length>0?t.wallpapers:t?.system_wallpapers)||[],u=e.entity.getPref("screensaver_mode"),p=e.entity.getPref("screensaver_style"),d=e.entity.getPref("docked_idle_timeout"),m=e.entity.getPref("screensaver_photo_clock"),_=String(u?.value??o.screensaver_mode??"Docked Only")==="Never",h=String(p?.value??o.screensaver_style??"Ambient Clock"),b=!_&&h==="Photo Frame",y=dn(m?.value??o.screensaver_photo_clock,!1),f=String(o.screensaver_photo_mode||"off"),k=String(o.screensaver_photo_source||""),w=String(o.screensaver_photo_collection||""),M=Array.isArray(o.screensaver_photo_ids)?o.screensaver_photo_ids:[],E=Number(o.screensaver_cycle_minutes??15),N=!!o.screensaver_shuffle,$=za(c,f,k,w,M,{excludeDynamic:!0}),P=Ol(e,f,k,w,$,c),H=[];i.active_screensaver_photo_thumb_url&&H.push(i.active_screensaver_photo_thumb_url);for(let F of $){let be=F.thumb_url||F.preview_url||"";be&&!H.includes(be)&&H.length<3&&H.push(be)}let C=!!i.screensaver_active,L=!!(u||p||d),D=e.entity.getPref("va_visual_profile"),z=!!(e.entity.getPref("bedtime_active")?.value??o.bedtime_active),Z=e.entity.getPref("auto_brightness_mode"),_e=String(Z?.value??"").trim(),Q=_e==="Disabled"||_e==="off",ee=_e==="Time Schedule",oe=_e==="Ambient Light",O=String(i.active_area_name||"").trim(),re=String(i.active_area_lux_display||"").trim(),K=i.active_area_ambient_pct!==null&&i.active_area_ambient_pct!==void 0?Number(i.active_area_ambient_pct):null,I;oe&&(re&&K!==null&&Number.isFinite(K)?I=e.t("dev_display.ambient_live_status",{area:O||e.t("common.unknown"),lux:re,level:A(K,e.hass,0)}):O&&O!=="Unassigned"?I=e.t("dev_display.ambient_fallback_status",{area:O}):I=e.t("dev_display.ambient_unassigned_status"));let X=e.entity.getPrefs(["auto_brightness_mode","manual_brightness","day_brightness","night_brightness","day_start_hour","night_start_hour"]).filter(F=>!(Z&&(Q&&(F.key==="day_brightness"||F.key==="night_brightness")||!Q&&F.key==="manual_brightness"||!ee&&(F.key==="day_start_hour"||F.key==="night_start_hour")))),ae=e.entity.getPref("color_profile"),he=Eo(e.host),ke=ue(he)?he.toUpperCase():Eo(null),ve=ue(o.device_custom_color)?String(o.device_custom_color).toUpperCase():ke,x=`--swatch-color:${ve}`,J=(e.entity.getPref("home_screen_enabled")?.value??o.home_screen_enabled)!==!1,fe=dn(e.entity.getPref("weather_background")?.value??o.weather_background,!0),Ee=dn(e.entity.getPref("weather_app_background")?.value??o.weather_app_background,!0),ze=String(o.wallpaper_mode||""),Le=String(o.wallpaper_source||""),Ke=String(o.wallpaper_collection||""),Y=Array.isArray(o.wallpaper_favorites)?o.wallpaper_favorites:[],le=Number(o.wallpaper_cycle_minutes||0),ne=ze||(Le?"single":Y.length>0&&le>0?"custom":"off"),He=za(c,ne,Le,Ke,Y),Ie=c.find(F=>F.id===i.active_wallpaper_id)||c.find(F=>!!F.active)||He[0]||null,We=ne!=="off"&&(!!Ie||He.length>0),St=Ol(e,ne,Le||Ie?.id||"",Ke,He,c),Oe=[];i.active_wallpaper_thumb_url?Oe.push(i.active_wallpaper_thumb_url):(Ie?.thumb_url||Ie?.preview_url)&&Oe.push(Ie.thumb_url||Ie.preview_url||"");for(let F of He){let be=F.thumb_url||F.preview_url||"";be&&!Oe.includes(be)&&Oe.length<3&&Oe.push(be)}let ie="";if(We){let F=J&&fe;F&&Ee?ie=e.t("dev_display.wp_override_home_and_weather"):F?ie=e.t("dev_display.wp_override_home_only"):Ee&&(ie=e.t("dev_display.wp_override_weather_only"))}return l`<section id="view-display">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${L?U({id:"card-screensaver",heading:l`<h3 class="card-title">${e.t("card.screensaver")}</h3>`,contentClass:"stack",body:l`<div class="settings-list">
                  ${u?pe(e,u):v}
                  ${!_&&p?pe(e,p):v}
                  ${!_&&d?pe(e,d):v}
                </div>

                ${b?l`<div id="screensaver-photo-frame-section" class="stack">
                      <div class="photo-pool-preview">
                        ${H.length>0?l`<div class="photo-pool-thumbs">
                              ${H.map(F=>l`<img
                                  src=${F}
                                  alt=""
                                  loading="lazy"
                                  class="photo-pool-thumb ${r}"
                                />`)}
                            </div>`:v}
                        <div class="photo-pool-info">
                          <span class="photo-pool-title">
                            ${e.t("dev_display.screensaver_pool_label")}
                          </span>
                          <span class="photo-pool-meta">
                            ${$.length>0?P.meta:e.t("dev_display.screensaver_pool_empty")}
                          </span>
                        </div>
                        <div class="photo-pool-actions">
                          <button
                            type="button"
                            id="btn-choose-ss-photos"
                            @click=${()=>e.entity.openPhotoPickerModal("screensaver")}
                            class="btn btn-secondary btn-compact"
                          >
                            ${e.t("dev_display.screensaver_choose_photos")}
                          </button>
                        </div>
                      </div>

                      <div class="settings-list">
                        ${R({label:e.tPrefLabel("screensaver_cycle_minutes"),forId:"cfg-screensaver_cycle_minutes",control:l`<select
                            id="cfg-screensaver_cycle_minutes"
                            .value=${S(String(E))}
                            @change=${F=>{e.entity.setScreensaverRotation(Number(F.currentTarget.value)||0)}}
                          >
                            ${$o.map(F=>l`<option
                                value=${String(F.value)}
                                .selected=${S(F.value===E)}
                              >
                                ${Ll(e,F.value,F.label)}
                              </option>`)}
                          </select>`})}
                        ${j({id:"cfg-screensaver_shuffle",label:e.tPrefLabel("screensaver_shuffle"),description:e.t("dev_display.screensaver_shuffle_desc"),checked:N,onChange:F=>{e.entity.setScreensaverRotation(E,F)}})}
                        ${m?pe(e,m):j({id:"cfg-screensaver_photo_clock",label:e.tPrefLabel("screensaver_photo_clock"),description:e.t("dev_display.screensaver_photo_clock_desc"),checked:y,onChange:F=>e.entity.stageDeviceSetting("screensaver_photo_clock",F,"cfg-screensaver_photo_clock")})}
                      </div>
                    </div>`:v}

                ${_?v:l`<div class="settings-list">
                      ${R({id:"row-screensaver-preview",label:C?e.t("dev_overview.qa_exit_screensaver"):e.t("dev_overview.qa_activate_screensaver"),description:C?e.t("dev_display.screensaver_exit_desc"):e.t("dev_display.screensaver_preview_desc"),control:l`<button
                          type="button"
                          id="btn-screensaver-preview"
                          ?disabled=${s}
                          @click=${()=>{let F=C?"deactivate_screensaver":"activate_screensaver",be=C?e.t("dev_overview.qa_exit_screensaver"):e.t("dev_overview.qa_activate_screensaver");e.entity.runDeviceAction(F,e.t("sync.triggered_action",{label:be}))}}
                          class="btn btn-secondary btn-compact"
                        >
                          ${C?e.t("dev_display.exit_screensaver_btn"):e.t("dev_display.preview_btn")}
                        </button>`})}
                    </div>`}`}):v}

        ${D?U({heading:l`<h3 class="card-title">
                ${e.t("dev_display.card_voice_assistant")}
              </h3>`,contentClass:"settings-list",body:pe(e,D)}):v}

        ${X.length?U({id:"card-brightness",heading:l`<h3 class="card-title">${e.t("card.brightness")}</h3>`,subtitle:z?e.t("dev_display.bedtime_brightness_override_note"):I,contentClass:"settings-list",body:X.map(F=>{let be=oe&&F.key==="day_brightness"?e.t("dev_display.bright_brightness_label"):oe&&F.key==="night_brightness"?e.t("dev_display.dark_brightness_label"):void 0;return pe(e,F,be)})}):v}
      </div>

      <div class="column">
        ${U({heading:l`<h3 class="card-title">${e.t("card.colors")}</h3>`,contentClass:"settings-list",body:l`${ae?pe(e,ae):v}
            ${R({label:e.t("dev_display.custom_color_label"),forId:"dev-custom-palette-select",description:e.t("dev_display.custom_color_desc"),control:l`<span class="swatch" style=${x} aria-hidden="true"></span>
                <select
                  id="dev-custom-palette-select"
                  .value=${S(ve)}
                  @change=${F=>{let be=F.currentTarget.value;ue(be)&&e.entity.applyDeviceCustomColor(be,!0)}}
                >
                  ${a.length?l`
                        ${a.some(F=>F.hex.toUpperCase()===ve)?v:l`<option value=${ve} .selected=${S(!0)}>
                              ${e.t("dev_display.current_color_option",{hex:ve})}
                            </option>`}
                        ${a.map(F=>{let be=F.hex.toUpperCase();return l`<option value=${be} .selected=${S(be===ve)}>
                            ${F.name||be} (${be})
                          </option>`})}
                      `:l`<option value=${ve} .selected=${S(!0)}>
                        ${e.t("dev_display.current_color_option",{hex:ve})}
                      </option>`}
                </select>
                <button
                  type="button"
                  @click=${()=>e.tools.openColorWheelModal("device")}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("dev_display.add_color_btn")}
                </button>`})}`})}

        ${U({id:"card-device-wallpapers",heading:l`<h3 class="card-title">${e.t("card.wallpapers")}</h3>`,subtitle:e.t("dev_display.wallpapers_subtitle"),headerActions:l`<button
            type="button"
            id="btn-manage-photo-library"
            @click=${()=>e.openSystemSection("photos")}
            class="btn btn-text btn-compact"
          >
            ${e.t("dev_display.manage_photo_library")}
          </button>`,contentClass:"stack",body:l`<div id="wp-status-row" class="photo-pool-preview">
              ${Oe.length>0?l`<div class="photo-pool-thumbs">
                    ${Oe.map(F=>l`<img
                        src=${F}
                        alt=""
                        loading="lazy"
                        class="photo-pool-thumb ${r}"
                      />`)}
                  </div>`:v}
              <div class="photo-pool-info">
                <span class="photo-pool-title">${St.title}</span>
                <span class="photo-pool-meta">${St.meta}</span>
              </div>
              <div class="photo-pool-actions">
                <button
                  type="button"
                  id="btn-choose-wallpaper"
                  @click=${()=>e.entity.openPhotoPickerModal("wallpaper")}
                  class="btn btn-primary btn-compact"
                >
                  ${e.t("dev_display.choose_wallpaper")}
                </button>
                ${We?l`<button
                      type="button"
                      id="btn-turn-off-wp"
                      @click=${()=>{e.entity.setDevicePhotoPool({target:"wallpaper",mode:"off",cycleMinutes:0},e.t("dev_display.turn_off_wallpaper"))}}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("dev_display.turn_off_wallpaper")}
                    </button>`:v}
              </div>
            </div>

            ${ne==="collection"||ne==="custom"||le>0?l`<div class="settings-list">
                  ${R({id:"wp-rotation-row",label:e.t("dev_display.rotation_interval_label"),forId:"cfg-wallpaper_cycle_minutes",control:l`<select
                      id="cfg-wallpaper_cycle_minutes"
                      aria-label=${e.t("dev_display.rotation_interval_aria")}
                      .value=${S(String(le))}
                      @change=${F=>{e.entity.setWallpaperRotation(Number(F.currentTarget.value)||0)}}
                    >
                      ${$o.map(F=>l`<option
                          value=${String(F.value)}
                          .selected=${S(F.value===le)}
                        >
                          ${Ll(e,F.value,F.label)}
                        </option>`)}
                    </select>`})}
                </div>`:v}

            ${ie?l`<div id="wp-weather-override-note" class="alert">
                  <div class="alert-body">
                    <span>${ie}</span>
                  </div>
                  <button
                    type="button"
                    id="btn-wp-open-interface"
                    @click=${()=>e.openDeviceSection("interface","card-home-screen")}
                    class="btn btn-text btn-compact"
                  >
                    ${e.t("dev_display.open_interface")}
                  </button>
                </div>`:v}`})}
      </div>
    </div>
  </section>`}var Vd=new Set(["UTC","Etc/UTC","GMT","Etc/GMT","Etc/GMT+0","Etc/GMT-0","Etc/GMT0"]),qd=/^[A-Za-z0-9_+-]+(?:\/[A-Za-z0-9_+-]+)+$/;function Gd(e){let t=0,o=new Set;for(let i of String(e??"").split(";")){let a=i.trim();if(!a)continue;let n=a.indexOf("|");if(n<0)continue;let s=a.slice(0,n).trim(),r=a.slice(n+1).trim();if(!r||Vd.has(r)||!qd.test(r))continue;let c=`${s.toLowerCase()}|${r}`;if(!o.has(c)&&(o.add(c),t+=1,t>=4))break}return t}function Ni(e){return Ja(e)}function Nl(e,t,o){let i=`dev_interface.activity_src_${t}`,a=e.t(i);return a===i?o:a}function Hl(e){let t=e.state,o=t?.config||{},i=t?.capabilities||{},a=t?.system_config?.remote_groups||[],n=e.entity.getPref("home_screen_enabled"),s=n?!!n.value:o.home_screen_enabled!==!1,r=e.entity.getPref("start_screen"),c=r?.options&&r.options.length>0?r.options:Zn,u=(s?c:c.filter(T=>T!=="Home")).map(T=>({value:T,label:e.tPrefOption("start_screen",T)})),p=String(r?.value??o.start_screen??(s?"Home":"Time App")),d=!s&&p==="Home"?"Time App":p,m=s?null:Yn[d]||null,g=e.entity.getPref("home_clock_tap_action"),_=(g?.options&&g.options.length>0?g.options:Xn).map(T=>({value:T,label:e.tPrefOption("home_clock_tap_action",T)})),h=String(g?.value??o.home_clock_tap_action??"Time App"),b=e.entity.getPref("home_date_tap_action"),y=(b?.options&&b.options.length>0?b.options:Jn).map(T=>({value:T,label:e.tPrefOption("home_date_tap_action",T)})),f=String(b?.value??o.home_date_tap_action??"Overview"),k=e.entity.getPref("return_to_home_timeout"),w=(k?.options&&k.options.length>0?k.options:es).map(T=>({value:T,label:e.tPrefOption("return_to_home_timeout",T)})),M=String(k?.value??o.return_to_home_timeout??"2 min"),E=o.activity_card!==!1,N=e.entity.getEnabledActivitySources(),$=new Set(N),P=new Map(ut.map(T=>[T.token,T])),H=[...N.map(T=>P.get(T)).filter(T=>!!(T&&me(T,i))).map(T=>({token:T.token,label:Nl(e,T.token,T.label),enabled:!0})),...ut.filter(T=>!$.has(T.token)&&me(T,i)).map(T=>({token:T.token,label:Nl(e,T.token,T.label),enabled:!1}))],C=e.entity.getDockItems(),L=e.entity.getPinnedItems(),D=e.entity.getEnabledHomeCategories(),z=e.entity.getEnabledAreaCategories(),Z=e.entity.getEnabledToolsItems(),_e=new Map(it.map(T=>[T.token,T])),Q=Z.filter(T=>{let W=_e.get(T);return W?me(W,i):!0}).length,ee=e.entity.getEnabledGamesItems(),oe=(t?.system_devices||[]).find(T=>T.subentry_id===e.activeSubentryId),O=String(o.device_remote_group||oe?.device_remote_group||"area_auto").trim()||"area_auto",re=e.entity.getPref("album_art_style"),K=String(re?.value??o.album_art_style??"Full Screen"),I=e.tPrefOption("album_art_style",K),q=e.entity.getPref("album_sort_order"),X=String(q?.value??o.album_sort_order??"Alphabetical"),ae=e.tPrefOption("album_sort_order",X),he=e.entity.getPref("show_utc_clock"),ke=he?!!he.value:!!o.show_utc_clock,ve=e.entity.getPref("world_clocks"),x=Gd(ve?.value??o.world_clocks??""),J=e.entity.getPref("clock_face"),fe=e.entity.getPrefSpec("clock_face"),Ee=J?.options&&J.options.length>0?J.options:fe?.options||[],ze=i.is_round===!1?Ee.filter(T=>T!=="Modern Analog"):Ee,Le=String(J?.value??o.clock_face??"Minimal Digital"),Ke=(ze.length>0&&!ze.includes(Le)?ze[0]:void 0)??Le,Y=ze.map(T=>({value:T,label:e.tPrefOption("clock_face",T)})),le=e.tPrefOption("clock_face",Ke),ne=e.entity.getPref("time_format"),He=e.entity.getPrefSpec("time_format"),Ie=ne?.options&&ne.options.length>0?ne.options:He?.options||[],We=ne?.value??o.time_format,St=We!=null&&String(We).trim()!==""?String(We):$e(e.hass),Oe=(Ie.length>0&&!Ie.includes(St)?Ie[0]:void 0)??St,ie=Ie.map(T=>({value:T,label:e.tPrefOption("time_format",T)})),F=Oe.startsWith("24")?e.t("dev_interface.clock_24h"):e.t("dev_interface.clock_12h"),ro=e.entity.getPref("wake_greeting")?.value??o.wake_greeting,hc=ro!=null?typeof ro=="string"?!["","0","false","off","disabled"].includes(ro.trim().toLowerCase()):!!ro:!0,lo=e.entity.getPref("weather_background")?.value??o.weather_background,bn=lo!=null?typeof lo=="string"?!["","0","false","off","disabled"].includes(lo.trim().toLowerCase()):!!lo:!0,vc=["home_sun","home_moon"].map(T=>{let W=e.entity.getPref(T),ce=W?.value??o[T],Me=ce!=null?typeof ce=="string"?!["","0","false","off","disabled"].includes(ce.trim().toLowerCase()):!!ce:!0;return{token:T,label:e.tPrefLabel(T,W?.label),enabled:Me}}),fn=()=>Y.length>0?se({id:"cfg-clock_face",label:e.tPrefLabel("clock_face"),description:e.t("dev_interface.clock_face_desc"),value:Ke,rawOptions:Y,onChange:T=>{e.entity.stageDeviceSetting("clock_face",T,"cfg-clock_face")}}):v,bc=e.entity.getPref("calendar_lookahead_days"),Ki=Number(bc?.value??o.calendar_lookahead_days??30),fc=Ki<=10?7:Ki<=21?14:Ki<=45?30:60,qo=e.entity.getPref("calendar_week_start")?.value??o.calendar_week_start,yc=qo!=null&&String(qo).trim()!==""?String(qo):ms(e.hass),wc=e.tPrefOption("calendar_week_start",yc==="Monday"?"Monday":"Sunday"),Sc=e.entity.getSystemCameraEntities(),yn=e.entity.getVisibleCameras(),kc=e.entity.getPref("camera_default_view"),$c=String(kc?.value??o.camera_default_view??"Grid"),wn=e.tPrefOption("camera_default_view",$c),Cc=e.entity.getPref("camera_framing"),Tc=String(Cc?.value??o.camera_framing??"Uncropped"),Sn=e.tPrefOption("camera_framing",Tc),co=e.entity.getPref("weather_app_background")?.value??o.weather_app_background,xc=co!=null?typeof co=="string"?!["","0","false","off","disabled"].includes(co.trim().toLowerCase()):!!co:!0,kn=T=>{switch(T){case"app:pinned":{if(L.length===0)return e.t("dev_interface.pinned_empty_meta");let W=Math.ceil(L.length/6);return e.t("dev_interface.pinned_count_meta",{count:A(L.length,e.hass,0),shortcutWord:L.length===1?e.t("dev_interface.word_shortcut_one"):e.t("dev_interface.word_shortcut_many"),pages:A(W,e.hass,0),pageWord:W===1?e.t("dev_interface.word_page_one"):e.t("dev_interface.word_page_many")})}case"app:music":return e.t("dev_interface.music_meta",{art:I,albums:ae});case"app:home_hub":return D.length===1?e.t("dev_interface.categories_enabled_one"):e.t("dev_interface.categories_enabled_many",{count:A(D.length,e.hass,0)});case"app:cameras":return Sc.length===0?e.t("dev_interface.cameras_empty_meta"):yn.length===1?e.t("dev_interface.cameras_meta_one",{view:wn,framing:Sn}):e.t("dev_interface.cameras_meta_many",{view:wn,framing:Sn,count:A(yn.length,e.hass,0)});case"app:area":return z.length===1?e.t("dev_interface.categories_enabled_one"):e.t("dev_interface.categories_enabled_many",{count:A(z.length,e.hass,0)});case"app:remote":{if(O==="all")return e.t("dev_interface.remote_all");if(O.startsWith("group:")){let W=O.slice(6);return a.find(ce=>ce.id===W)?.name||W}return e.t("dev_interface.remote_follow_area")}case"app:weather":return xc?e.t("dev_interface.weather_meta_live_sky"):e.t("dev_interface.weather_meta_wallpaper");case"app:time":return ke&&x>0?x===1?e.t("dev_interface.time_utc_world_one"):e.t("dev_interface.time_utc_world_many",{count:A(x,e.hass,0)}):x>0?x===1?e.t("dev_interface.time_world_one"):e.t("dev_interface.time_world_many",{count:A(x,e.hass,0)}):ke?e.t("dev_interface.time_local_utc"):e.t("dev_interface.time_local");case"app:clock":return`${le} \u2022 ${F}`;case"app:calendar":return e.t("dev_interface.calendar_meta",{days:A(fc,e.hass,0),weekday:wc});case"app:tools":return Q===1?e.t("dev_interface.tools_enabled_one"):e.t("dev_interface.tools_enabled_many",{count:A(Q,e.hass,0)});case"app:games":return ee.length===1?e.t("dev_interface.games_enabled_one"):e.t("dev_interface.games_enabled_many",{count:A(ee.length,e.hass,0)});default:return T}},Ac=new Map((t?.catalog?.shortcut_entities||[]).map(T=>[T.id,T])),Wi=new Map(Be.map(T=>[T.token,T])),Ec=new Set(C.filter(T=>Ni(T)).map(T=>T.target)),$n=Ue.filter(T=>!Ec.has(T)),Ic=(()=>{let T=new Map;return C.map(W=>{let ce=Ni(W)?`native:${W.target}`:`custom:${W.kind}:${W.target}:${W.action}:${W.label}:${W.icon}`,Me=(T.get(ce)||0)+1;return T.set(ce,Me),Me===1?ce:`${ce}#${Me}`})})(),ji=T=>{if(Ni(T))return{title:Wi.get(T.target)?.label||T.target,meta:kn(T.target),icon:nt[T.target]||"mdi:apps"};if(T.kind==="route"){let uo=Wi.get(T.target),Pc=T.label||uo?.label||T.target,Mc=uo?`${uo.group} \u2022 ${uo.label}`:T.target;return{title:Pc,meta:e.t("dev_interface.custom_route_meta",{target:Mc}),icon:T.icon||nt[T.target]||"mdi:apps"}}let W=Ac.get(T.target),ce=T.target.split(".",1)[0]||"",Me=bi(ce,T.action),Ut=T.label||W?.name||T.target,Yi=T.confirm?e.t("dev_interface.custom_entity_confirm_meta",{action:Me,target:T.target}):e.t("dev_interface.custom_entity_tap_meta",{action:Me,target:T.target});return{title:Ut,meta:Yi,icon:T.icon||W?.icon||"mdi:flash"}};return l`<section id="view-interface">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${U({id:"card-home-screen",heading:l`<h3 class="card-title">${e.t("card.home_screen")}</h3>`,contentClass:"settings-list",body:l`${j({id:"cfg-home_screen_enabled",label:e.tPrefLabel("home_screen_enabled"),description:e.t("dev_interface.enable_home_desc"),checked:s,onChange:T=>{e.entity.stageDeviceSetting("home_screen_enabled",T,"cfg-home_screen_enabled")}})}
            ${R({label:e.tPrefLabel("start_screen"),forId:"cfg-start_screen",description:s?e.t("dev_interface.start_screen_multi_desc"):e.t("dev_interface.start_screen_single_desc"),control:l`<select
                  id="cfg-start_screen"
                  .value=${S(d)}
                  @change=${T=>{e.entity.stageDeviceSetting("start_screen",T.currentTarget.value,"cfg-start_screen")}}
                >
                  ${u.map(T=>l`<option value=${T.value} .selected=${S(T.value===d)}>
                        ${T.label}
                      </option>`)}
                </select>
                ${m?l`<button
                      type="button"
                      id="btn-configure-start-screen"
                      @click=${()=>e.entity.openAppConfigModal(m)}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("action.configure")}
                    </button>`:v}`})}
            ${ie.length>0?se({id:"cfg-time_format",label:e.tPrefLabel("time_format"),description:e.t("dev_interface.time_format_desc"),value:Oe,rawOptions:ie,onChange:T=>{e.entity.stageDeviceSetting("time_format",T,"cfg-time_format")}}):v}
            ${!s&&d==="Clock Face"?fn():v}
            ${s?l`${se({id:"cfg-home_clock_tap_action",label:e.tPrefLabel("home_clock_tap_action"),description:e.t("dev_interface.home_clock_tap_desc"),value:h,rawOptions:_,onChange:T=>{e.entity.stageDeviceSetting("home_clock_tap_action",T,"cfg-home_clock_tap_action")}})}
                  ${h==="Clock Face"||d==="Clock Face"?fn():v}
                  ${se({id:"cfg-home_date_tap_action",label:e.tPrefLabel("home_date_tap_action"),description:e.t("dev_interface.home_date_tap_desc"),value:f,rawOptions:y,onChange:T=>{e.entity.stageDeviceSetting("home_date_tap_action",T,"cfg-home_date_tap_action")}})}
                  ${se({id:"cfg-return_to_home_timeout",label:e.tPrefLabel("return_to_home_timeout"),description:e.t("dev_interface.return_timeout_desc"),value:M,rawOptions:w,onChange:T=>{e.entity.stageDeviceSetting("return_to_home_timeout",T,"cfg-return_to_home_timeout")}})}
                  ${j({id:"cfg-wake_greeting",label:e.tPrefLabel("wake_greeting"),description:e.t("dev_interface.wake_greeting_desc"),checked:hc,onChange:T=>{e.entity.stageDeviceSetting("wake_greeting",T,"cfg-wake_greeting")}})}
                  ${j({id:"cfg-weather_background",label:e.tPrefLabel("weather_background"),description:e.t("dev_interface.weather_bg_desc"),checked:bn,onChange:T=>{e.entity.stageDeviceSetting("weather_background",T,"cfg-weather_background")}})}
                  ${bn?R({id:"weather-celestial-bodies",label:e.t("dev_interface.sun_moon_label"),description:e.t("dev_interface.sun_moon_desc"),control:Ve({id:"weather-celestial-pills",ariaLabel:e.t("dev_interface.sun_moon_label"),items:vc,onToggle:(T,W)=>{e.entity.stageDeviceSetting(T,W)},overlay:e.localeOverlay})}):v}
                  ${j({id:"cfg-activity_card",label:e.tPrefLabel("activity_card"),description:e.t("dev_interface.activity_card_desc"),checked:E,onChange:T=>e.entity.stageDeviceSetting("activity_card",T,"cfg-activity_card")})}
                  ${E?R({id:"activity-sources",label:e.tPrefLabel("activity_sources"),description:e.t("dev_interface.activity_sources_desc"),stacked:!0,control:Ve({id:"activity-sources-pills",ariaLabel:e.tPrefLabel("activity_sources"),items:H,onToggle:(T,W)=>{e.entity.toggleActivitySource(T,W)},onReorder:(T,W)=>{e.entity.reorderActivitySources(T,W)},overlay:e.localeOverlay})}):v}`:v}`})}
      </div>

      <div class="column">
        ${s?U({id:"card-app-dock",heading:l`<h3 class="card-title">${e.t("card.app_dock")}</h3>`,contentClass:"stack",body:l`<p class="row-description">
                  ${e.t("dev_interface.app_dock_desc")}
                </p>
                <div id="dock-shortcuts-container" class="stack">
                  ${Fe({id:"dock-shortcuts-list",ariaLabel:e.t("dev_interface.active_dock_aria"),items:C,rowClass:"dock-row",getKey:(T,W)=>Ic[W]??String(W),getLabel:T=>ji(T).title,onReorder:(T,W)=>{e.entity.reorderShortcutItems("dock_items",T,W)},renderContent:T=>{let W=ji(T);return l`<div class="input-action-row">
                        <span
                          class=${Bt(T.badge_style,T.accent)}
                          aria-hidden="true"
                        >
                          <ha-icon .icon=${W.icon}></ha-icon>
                        </span>
                        <div class="shortcut-item-info">
                          <span class="shortcut-item-title">${W.title}</span>
                          <span class="shortcut-item-meta">${W.meta}</span>
                        </div>
                      </div>`},renderActions:(T,W)=>{let ce=ji(T);if(Ni(T)){let Me=Sa[T.target];return l`${Me?l`<button
                                type="button"
                                aria-label=${e.t("action.configure_item",{item:ce.title})}
                                @click=${()=>e.entity.openAppConfigModal(Me)}
                                class="btn btn-secondary btn-compact"
                              >
                                ${e.t("action.configure")}
                              </button>`:v}
                          <input
                            type="checkbox"
                            role="switch"
                            aria-label=${e.t("dev_interface.show_on_dock_aria",{title:ce.title})}
                            .checked=${S(!0)}
                            @change=${Ut=>e.entity.toggleNativeDockApp(T.target,Ut.currentTarget.checked)}
                            class="switch"
                          />`}return l`<button
                          type="button"
                          aria-label=${e.t("action.edit_item",{item:ce.title})}
                          @click=${()=>e.entity.openShortcutModal("dock_items",W)}
                          class="btn btn-secondary btn-compact"
                        >
                          ${e.t("action.edit")}
                        </button>
                        ${Se(e.t("action.remove_item",{item:ce.title}),()=>e.entity.removeShortcutItem("dock_items",W))}`},overlay:e.localeOverlay})}
                  <div class="dock-row shortcut-item-locked">
                    <span class="shortcut-icon-badge" aria-hidden="true">
                      <ha-icon .icon=${"mdi:cog"}></ha-icon>
                    </span>
                    <div class="shortcut-item-info">
                      <span class="shortcut-item-title">
                        ${e.t("dev_interface.settings_title")}
                      </span>
                      <span class="shortcut-item-meta">
                        ${e.t("dev_interface.settings_locked_meta")}
                      </span>
                    </div>
                  </div>
                </div>
                <div class="shortcut-toolbar">
                  <button
                    type="button"
                    id="btn-add-dock-item"
                    ?disabled=${C.length>=at}
                    @click=${()=>e.entity.openShortcutModal("dock_items",null)}
                    class="btn btn-secondary"
                  >
                    ${e.t("action.add_custom_shortcut")}
                  </button>
                  <button
                    type="button"
                    id="btn-reset-dock-items"
                    @click=${()=>e.entity.requestResetDockItems()}
                    class="btn btn-text"
                  >
                    ${e.t("action.reset_default_dock")}
                  </button>
                </div>
                ${$n.length>0?l`<div
                      id="dock-hidden-native-apps"
                      class="stack"
                      role="group"
                      aria-label=${e.t("dev_interface.hidden_from_dock")}
                    >
                      <div class="subsection-title">
                        ${e.t("dev_interface.hidden_from_dock")}
                      </div>
                      ${ge($n,T=>T,T=>{let ce=Wi.get(T)?.label||T,Me=nt[T]||"mdi:apps",Ut=Sa[T];return l`<div class="dock-row shortcut-item-hidden">
                            <span class="shortcut-icon-badge" aria-hidden="true">
                              <ha-icon .icon=${Me}></ha-icon>
                            </span>
                            <div class="shortcut-item-info">
                              <span class="shortcut-item-title">${ce}</span>
                              <span class="shortcut-item-meta">${kn(T)}</span>
                            </div>
                            ${Ut?l`<button
                                  type="button"
                                  aria-label=${e.t("action.configure_item",{item:ce})}
                                  @click=${()=>e.entity.openAppConfigModal(Ut)}
                                  class="btn btn-secondary btn-compact"
                                >
                                  ${e.t("action.configure")}
                                </button>`:v}
                            <input
                              type="checkbox"
                              role="switch"
                              aria-label=${e.t("dev_interface.show_on_dock_aria",{title:ce})}
                              ?disabled=${C.length>=at}
                              .checked=${S(!1)}
                              @change=${Yi=>e.entity.toggleNativeDockApp(T,Yi.currentTarget.checked)}
                              class="switch"
                            />
                          </div>`})}
                    </div>`:v}`}):v}
      </div>
    </div>
  </section>`}function Ul(e,t){let{curDevEntry:o,isBleOnly:i}=t,a=e.state,n=a?.config||{},s=a?.capabilities||{},r=String(n.effective_ble_category||o?.ble_category||"ble_tag"),c=String(n.ble_category||"auto").trim().toLowerCase(),u=c==="phone"||c==="ble_tag"?c:"auto",p=a?.device_groups||[],d=String(n.device_group||"custom").trim()||"custom",m=d==="custom"||p.some(b=>b.id===d)?d:"custom",g=a?.system_config?.remote_groups||[],_=String(n.device_remote_group||o?.device_remote_group||"area_auto").trim()||"area_auto",h=e.t("dev_overview.remote_follow_area");if(_==="all")h=e.t("dev_overview.remote_all_system");else if(_.startsWith("group:")){let b=_.slice(6);h=g.find(y=>y.id===b)?.name||b}return U({id:"card-device-assignments",title:e.t("card.assignments"),contentClass:"settings-list",body:l`${i?R({label:e.t("dev_overview.device_category_label"),forId:"cfg-ble_category",description:e.t("dev_overview.device_category_desc"),control:l`<select
              id="cfg-ble_category"
              .value=${S(u)}
              @change=${b=>e.entity.stageDeviceSetting("ble_category",b.currentTarget.value,"cfg-ble_category")}
            >
              <option value="auto" .selected=${S(u==="auto")}>
                ${e.t("dev_overview.auto_category_option",{category:r==="phone"?e.t("status.phone"):e.t("status.ble_tag")})}
              </option>
              <option value="phone" .selected=${S(u==="phone")}>
                ${e.t("status.phone")}
              </option>
              <option value="ble_tag" .selected=${S(u==="ble_tag")}>
                ${e.t("status.ble_tag")}
              </option>
            </select>`}):R({label:e.t("dev_overview.device_group_label"),forId:"cfg-device_group",description:m==="custom"?e.t("dev_overview.device_group_custom_desc"):e.t("dev_overview.device_group_preset_desc"),control:l`<select
                id="cfg-device_group"
                .value=${S(m)}
                @change=${b=>e.entity.stageDeviceSetting("device_group",b.currentTarget.value,"cfg-device_group")}
              >
                <option value="custom" .selected=${S(m==="custom")}>
                  ${e.t("common.custom")}
                </option>
                ${p.map(b=>l`<option value=${b.id} .selected=${S(b.id===m)}>
                      ${b.name}
                    </option>`)}
              </select>
              ${m==="custom"?l`<button
                    type="button"
                    id="btn-save-custom-group"
                    @click=${()=>e.groups.openSaveGroupModal()}
                    class="btn btn-secondary btn-compact"
                  >
                    ${e.t("action.save_custom_group")}
                  </button>`:v}
              <button
                type="button"
                id="btn-manage-groups"
                @click=${()=>e.openManageGroups(m)}
                class="btn btn-text btn-compact"
              >
                ${e.t("action.manage_groups")}
              </button>`})}
      ${se({id:"cfg-assigned_person",label:e.t("dev_overview.assigned_person_label"),description:e.t("dev_overview.assigned_person_desc"),value:n.assigned_person,choices:a?.catalog?.persons,emptyOptionLabel:e.t("dev_overview.unassigned_option"),onChange:b=>e.entity.stageDeviceSetting("assigned_person",b,"cfg-assigned_person")})}
      ${!i&&s.has_display?R({label:e.t("dev_overview.remote_group_label"),description:e.t("dev_overview.remote_group_desc"),control:l`<span class="chip">${h}</span>
              <button
                type="button"
                id="btn-configure-remote-group"
                @click=${()=>e.entity.openAppConfigModal("remote")}
                class="btn btn-text btn-compact"
              >
                ${e.t("action.configure")}
              </button>`}):v}`})}function Hi(e){if(e.device_command)return e.device_command;if(e.device_class==="identify")return"find_my";if(e.device_class==="restart")return"restart";let t=(e.key||e.entity_id.split(".",2)[1]||"").toLowerCase();return t==="find_my"||t.endsWith("_find_my_device")||t.endsWith("_find_my")?"find_my":t==="trigger_va"||t.endsWith("_trigger_voice_assistant")||t.endsWith("_trigger_va")?"trigger_va":t==="activate_screensaver"||t.endsWith("_activate_screensaver")?"activate_screensaver":t==="deactivate_screensaver"||t.endsWith("_deactivate_screensaver")?"deactivate_screensaver":t==="hibernate"||t.endsWith("_hibernate_device")||t.endsWith("_hibernate")?"hibernate":t==="restart"||t.endsWith("_restart_device")||t.endsWith("_restart")?"restart":""}function zd(e,t,o){switch(t){case"find_my":return e.t("dev_overview.qa_find_my");case"trigger_va":return e.t("dev_overview.qa_trigger_va");case"activate_screensaver":return e.t("dev_overview.qa_activate_screensaver");case"deactivate_screensaver":return e.t("dev_overview.qa_exit_screensaver");case"restart":return e.t("dev_overview.qa_restart");default:return te(o)}}function Fl(e,t){let{isBleOnly:o,isOffline:i,hasOpenInHa:a}=t;if(o)return v;let n=e.state,s=e.entity.getSectionItems("actions").concat(e.entity.getSectionItems("overview")),r=s.filter(k=>k.domain==="button"),c=(n?.quick_actions||[]).map(k=>{let w=k.device_command||k.key;return{entity_id:`cmd:${k.key}`,domain:"button",name:zd(e,w,k.label),state:k.state,key:k.key,device_command:k.device_command,device_class:k.device_class||(w==="find_my"?"identify":w==="restart"?"restart":void 0)}}),u=new Set(c.map(k=>Hi(k)).filter(Boolean)),p=r.filter(k=>{let w=Hi(k);return!w||!u.has(w)}),d=c.concat(p),m=d.filter(k=>Hi(k)!=="restart"),g=d.find(k=>Hi(k)==="restart")||null,_=s.filter(k=>k.domain!=="button");n?.speaker_volume&&!_.some(k=>k.entity_id===n.speaker_volume?.entity_id)&&_.push(n.speaker_volume);let h=e.entity.getPref("do_not_disturb"),b=i?_.map(k=>({...k,state:"unavailable"})):_,y=m.length>0||!!h||b.length>0||!!g,f=()=>{if(!g)return;let k=e.t("sync.restarting_device");g.device_command?e.entity.runDeviceAction(g.device_command,k):e.entity.espAction(g.entity_id,"press",void 0,k)};return U({id:"card-device-quick-actions",title:e.t("card.quick_actions"),contentClass:"settings-list",body:y?l`${As(e,m,i)}
          ${h?pe(e,h):v}
          ${b.map(k=>Ce(e,k))}
          ${g?R({id:"row-restart-device",label:e.t("dev_overview.restart_device"),description:e.t("dev_overview.restart_device_desc"),control:l`<button
                  type="button"
                  id="btn-restart-device"
                  data-entity-id=${g.entity_id}
                  ?disabled=${i||String(g.state??"")==="unavailable"}
                  @click=${f}
                  class="btn btn-danger btn-compact"
                >
                  ${e.t("dev_overview.restart_btn")}
                </button>`}):v}`:l`<p class="empty-state">${e.t("dev_overview.empty_quick_actions")}</p>`,footerActions:a?l`<button
          type="button"
          id="btn-open-in-ha"
          @click=${()=>e.openDeviceInHa()}
          class="btn btn-text"
        >
          ${e.t("action.open_in_ha")}
        </button>`:v})}var Kd="M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z",Wd="M16,20H8V6H16M16.67,4H15V2H9V4H7.33A1.33,1.33 0 0,0 6,5.33V20.67C6,21.4 6.6,22 7.33,22H16.67A1.33,1.33 0 0,0 18,20.67V5.33C18,4.6 17.4,4 16.67,4Z",jd="M16,7V3H14V7H10V3H8V7H8C7,7 6,8 6,9V14.5L9.5,18V21H14.5V18L18,14.5V9C18,8 17,7 16,7M16,13.67L12.5,17.17V19H11.5V17.17L8,13.67V9H16V13.67Z",Yd="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z",Zd="M12,21L15.6,16.2C14.6,15.45 13.35,15 12,15C10.65,15 9.4,15.45 8.4,16.2L12,21M12,3C7.95,3 4.21,4.34 1.2,6.6L3,9C5.5,7.12 8.62,6 12,6C15.38,6 18.5,7.12 21,9L22.8,6.6C19.79,4.34 16.05,3 12,3M12,9C9.3,9 6.81,9.89 4.8,11.4L6.6,13.8C8.1,12.67 9.97,12 12,12C14.03,12 15.9,12.67 17.4,13.8L19.2,11.4C17.19,9.89 14.7,9 12,9Z",Xd="M14.88,16.29L13,18.17V14.41M13,5.83L14.88,7.71L13,9.58M17.71,7.71L12,2H11V9.58L6.41,5L5,6.41L10.59,12L5,17.58L6.41,19L11,14.41V22H12L17.71,16.29L13.41,12L17.71,7.71Z",Jd="M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z",Qd="M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.9,2 2,2.9 2,4V11C2,11.55 2.22,12.05 2.59,12.42L11.59,21.42C11.95,21.78 12.45,22 13,22C13.55,22 14.05,21.78 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.45 21.77,11.94 21.41,11.58M13,20.01L4,11V4H11V3.99L20,12.99L13,20.01M6.5,5A1.5,1.5 0 0,1 8,6.5A1.5,1.5 0 0,1 6.5,8A1.5,1.5 0 0,1 5,6.5A1.5,1.5 0 0,1 6.5,5Z";function eu(e,t){return t===null||!Number.isFinite(t)?e.t("signal.no_reading"):t>=-60?e.t("signal.excellent"):t>=-70?e.t("signal.good"):t>=-80?e.t("signal.fair"):e.t("signal.weak")}function Vl(e,t){let{curDevEntry:o,winRow:i,isBleOnly:a,hasOpenInHa:n}=t,s=e.state,r=s?.config||{},c=s?.live||{},u=s?.capabilities||{},p=s?.esphome,d=!!(u.has_battery||o?.has_battery),m=!a&&d&&o?.battery_level!==null&&o?.battery_level!==void 0&&Number.isFinite(Number(o.battery_level)),g=m?Math.max(0,Math.min(100,Math.round(Number(o?.battery_level)))):0,_=`--signal-pct:${g}%`,h=o?.is_charging?e.t("status.charging"):o?.is_usb_connected?e.t("status.plugged_in"):m?e.t("status.on_battery"):e.t("dev_overview.waiting_for_reading"),b=null;!a&&o?.wifi_rssi!==null&&o?.wifi_rssi!==void 0?b=Number(o.wifi_rssi):a&&i&&i.effective_rssi!==null&&i.effective_rssi!==void 0&&(b=Number(i.effective_rssi));let y=b!==null&&Number.isFinite(b),f=y?`${A(b,e.hass,0)} dBm`:e.t("common.unknown"),w=`--signal-pct:${y?ui(b):0}%`,M=!!o?.has_assigned_area,E=M?o?.area_label||c.active_area_name||e.t("common.unknown"):c.active_area_name||e.t("common.unknown"),N=String(r.effective_ble_category||o?.ble_category||"ble_tag"),$=c.ble_closest_proxy&&i&&i.distance_m!==null&&i.distance_m!==void 0?` (~${zt(i.distance_m,e.hass,i.distance_ft)})`:"",P=!!((a||u.has_ble_beacon&&r.native_ble_tracking)&&c.ble_closest_proxy),H=a?N==="phone"?e.t("status.phone"):e.t("status.ble_tag"):M?e.t("status.stationary"):e.t("status.roaming"),C=P?`${H} \u2022 ${c.ble_closest_proxy}${$}`:H,L=String(c.device_sw_version||p?.device?.sw_version||"").replace(/^v/i,""),D=L?`v${L}`:e.t("common.unknown"),z=(p?.sections||[]).flatMap(q=>(q.items||[]).filter(X=>X.domain==="update")),Z=String(c.fw_update_entity||z[0]?.entity_id||"").trim(),_e=Z?z.find(q=>q.entity_id===Z):z[0],Q=String(_e?.state??(Z?e.hass?.states?.[Z]?.state:"")??"").trim(),ee=!!(Z&&Q&&Q!=="unavailable"&&Q!=="unknown"),oe=c.fw_update_available?e.t("status.update"):ee?e.t("status.up_to_date"):e.t("common.unknown"),O="chip",re="status-dot",K=e.t("common.unknown");a?o?.status_code==="online"||o?.is_online||i?(O="chip chip-success",re="status-dot online",K=e.t("status.online")):o?.status_code==="scanning"?K=e.t("status.scanning"):o?.status_code==="away"?K=e.t("status.away"):o?.status_label&&(K=o.status_label):o?.is_online&&c.fw_update_available?(O="chip chip-warning",re="status-dot update",K=e.t("status.update")):o?.is_online?(O="chip chip-success",re="status-dot online",K=e.t("status.online")):o?.is_online===!1&&(K=c.is_ble_sleep_expected?e.t("status.sleeping"):e.t("status.offline"));let I=d?l`<div class="status-tile-head">
          ${we(Wd)}
          <span>${e.t("dev_overview.tile_battery")}</span>
        </div>
        <strong class="status-tile-value">
          ${m?li(o?.battery_level,e.hass):e.t("common.unknown")}
        </strong>
        <span class="status-tile-meta">${h}</span>
        ${m?l`<div class="signal-track" aria-hidden="true">
              <div
                class="signal-fill${g<=20&&!o?.is_charging?" low":""}"
                style=${_}
              ></div>
            </div>`:v}`:l`<div class="status-tile-head">
          ${we(jd)}
          <span>${e.t("dev_overview.tile_power")}</span>
        </div>
        <strong class="status-tile-value">${e.t("status.plugged_in")}</strong>
        <span class="status-tile-meta">
          ${u.has_power?e.t("status.sleep_wake_active"):e.t("status.always_on")}
        </span>`;return U({id:"card-device-status",heading:l`<h3 class="card-title">${e.t("card.status")}</h3>`,headerActions:l`<span id="st-status-chip" class=${O}>
      <span class=${re} aria-hidden="true"></span>${K}
    </span>`,contentClass:"stack",body:l`<div class="status-tiles">
      <button
        type="button"
        @click=${()=>e.switchView("presence")}
        class="status-tile"
      >
        <div class="status-tile-head">
          ${we(Kd)}
          <span id="st-area-label">
            ${M?e.t("dev_overview.tile_area"):e.t("dev_overview.tile_current_area")}
          </span>
        </div>
        <strong class="status-tile-value">${E}</strong>
        <span class="status-tile-meta">${C}</span>
      </button>

      ${a?l`<button
            type="button"
            @click=${()=>e.switchView("presence")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${we(Yd)}
              <span>${e.t("dev_overview.tile_closest_proxy")}</span>
            </div>
            <strong class="status-tile-value">
              ${c.ble_closest_proxy||e.t("common.unknown")}
            </strong>
            <span class="status-tile-meta">
              ${i&&i.distance_m!==null&&i.distance_m!==void 0?`~${zt(i.distance_m,e.hass,i.distance_ft)}`:e.t("dev_overview.ble_presence_meta")}
            </span>
          </button>`:e.deviceHasView("power")?l`<button
              type="button"
              @click=${()=>e.switchView("power")}
              class="status-tile"
            >
              ${I}
            </button>`:l`<div class="status-tile">${I}</div>`}

      <button
        type="button"
        @click=${()=>a?e.switchView("presence"):e.openDeviceSection("tools","card-device-diagnostics")}
        class="status-tile"
      >
        <div class="status-tile-head">
          ${we(a?Xd:Zd)}
          <span id="st-wifi-label">
            ${a?e.t("dev_overview.tile_ble_signal"):e.t("dev_overview.tile_wifi_signal")}
          </span>
        </div>
        <strong class="status-tile-value">${f}</strong>
        <span class="status-tile-meta">${eu(e,b)}</span>
        ${y?l`<div class="signal-track" aria-hidden="true">
              <div
                class="signal-fill${b!==null&&b<-80?" low":""}"
                style=${w}
              ></div>
            </div>`:v}
      </button>

      ${a?l`<button
            type="button"
            @click=${()=>e.openDeviceSection("presence","card-ble-identity")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${we(Qd)}
              <span>${e.t("dev_overview.tile_ble_target")}</span>
            </div>
            <strong class="status-tile-value">
              <code>${r.ble_target_address||e.t("common.unknown")}</code>
            </strong>
            <span class="status-tile-meta">
              ${e.t("dev_overview.ble_address_meta")}
            </span>
          </button>`:l`<button
            type="button"
            @click=${()=>e.openDeviceSection("tools","card-device-diagnostics")}
            class="status-tile"
          >
            <div class="status-tile-head">
              ${we(Jd)}
              <span>${e.t("dev_overview.tile_firmware")}</span>
            </div>
            <strong class="status-tile-value">${D}</strong>
            <span class="status-tile-meta">${oe}</span>
          </button>`}
    </div>`,footerActions:a&&n?l`<button
            type="button"
            id="btn-open-in-ha"
            @click=${()=>e.openDeviceInHa(!0)}
            class="btn btn-text"
          >
            ${e.t("action.open_in_ha")}
          </button>`:v})}var un=[{time:"07:00",enabled:!1,recurrence:1},{time:"08:30",enabled:!1,recurrence:2},{time:"09:00",enabled:!1,recurrence:2}];function pn(e,t){let o=(e||"").trim(),i=/^(\d{1,2}):(\d{2})\|([01])\|([0-3])$/.exec(o);if(!i)return{...t};let a=Number(i[1]),n=Number(i[2]);return a<0||a>23||n<0||n>59?{...t}:{time:`${String(a).padStart(2,"0")}:${String(n).padStart(2,"0")}`,enabled:i[3]==="1",recurrence:Number(i[4])}}function ql(e){let o=String(e||ai).trim().split(";");return[pn(o[0],un[0]),pn(o[1],un[1]),pn(o[2],un[2])]}function Gl(e){return e.slice(0,3).map(t=>`${t.time}|${t.enabled?1:0}|${t.recurrence}`).join(";")}function mn(e){let t=Math.max(0,Math.floor(Number(e)||0)),o=Math.floor(t/3600),i=Math.floor(t%3600/60),a=t%60;return o>0?`${String(o).padStart(2,"0")}:${String(i).padStart(2,"0")}:${String(a).padStart(2,"0")}`:`${String(i).padStart(2,"0")}:${String(a).padStart(2,"0")}`}function zl(e,t){let{isBleOnly:o,isOffline:i}=t,a=e.state,n=a?.config||{},s=a?.live||{},r=a?.capabilities||{};if(o||!r.has_display)return v;let c=e.entity.getPref("alarms_summary"),u=ql(c?.value??n.alarms_summary??ai),p=(P,H,C)=>{let L=[{...u[0]},{...u[1]},{...u[2]}],D={...L[P],...H};/^\d{2}:\d{2}$/.test(D.time)&&(L[P]=D,e.entity.stageDeviceSetting("alarms_summary",Gl(L),C))},d=Number.isFinite(e.liveClockNowMs)?e.liveClockNowMs:Date.now(),m=s.timer_ends_at?Date.parse(s.timer_ends_at):Number.NaN,g=s.timer_running&&Number.isFinite(m)?Math.max(0,Math.ceil((m-d)/1e3)):Math.max(0,Math.round(Number(s.timer_remaining_sec||0))),_=s.stopwatch_started_at?Date.parse(s.stopwatch_started_at):Number.NaN,h=s.stopwatch_running&&Number.isFinite(_)?Math.max(0,Math.floor((d-_)/1e3)):Math.max(0,Math.round(Number(s.stopwatch_elapsed_sec||0))),b=!!(s.timer_running||s.timer_paused),y=!!(s.stopwatch_running||s.stopwatch_paused),f=!!s.alarm_ringing,k=u.filter(P=>P.enabled).sort((P,H)=>P.time.localeCompare(H.time)),w=Kt(e),M=k[0],E=M?e.t("dev_overview.alarms_enabled_summary",{count:A(k.length,e.hass,0),nextTime:ps(M.time,w)}):e.t("common.all_off"),N=M?"chip chip-primary":"chip",$=[{value:0,label:e.t("dev_overview.alarm_rec_daily")},{value:1,label:e.t("dev_overview.alarm_rec_weekdays")},{value:2,label:e.t("dev_overview.alarm_rec_weekends")},{value:3,label:e.t("dev_overview.alarm_rec_once")}];return U({id:"card-device-timers-alarms",title:e.t("card.timers_alarms"),body:l`${f?l`<div id="overview-ringing-alert" role="alert" class="alert alert-warning">
            <span>${e.t("dev_overview.ringing_alert_text")}</span>
            <button
              type="button"
              id="btn-dismiss-ringing"
              ?disabled=${i}
              @click=${()=>{e.entity.runDeviceAction("dismiss_ringing",e.t("dev_overview.dismissed_ringing_toast"))}}
              class="btn btn-secondary btn-compact"
            >
              ${e.t("action.dismiss")}
            </button>
          </div>`:v}
      <div class="settings-list">
        ${R({id:"overview-active-timer",label:e.t("dev_overview.active_timer_label"),description:b?void 0:e.t("dev_overview.no_active_timer"),control:b?l`<span class="chip ${s.timer_running?"chip-primary":""}">
                  ${s.timer_running?e.t("dev_overview.running"):e.t("dev_overview.paused")}
                </span>
                <strong class="kv-value">
                  ${mn(g)}
                </strong>
                <button
                  type="button"
                  id="btn-cancel-timer"
                  ?disabled=${i}
                  @click=${()=>{e.entity.runDeviceAction("cancel_timer",e.t("dev_overview.cancelled_timer_toast"))}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("dev_overview.cancel_timer")}
                </button>`:l`<span class="kv-value">${e.t("common.unknown")}</span>`})}
        ${R({id:"overview-stopwatch",label:e.t("dev_overview.stopwatch_label"),description:y?void 0:e.t("dev_overview.not_running"),control:y?l`<span class="chip ${s.stopwatch_running?"chip-primary":""}">
                  ${s.stopwatch_running?e.t("dev_overview.running"):e.t("dev_overview.paused")}
                </span>
                <strong class="kv-value">
                  ${mn(h)}
                </strong>
                <button
                  type="button"
                  id="btn-reset-stopwatch"
                  ?disabled=${i}
                  @click=${()=>{e.entity.runDeviceAction("reset_stopwatch",e.t("dev_overview.reset_stopwatch_toast"))}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("dev_overview.reset_stopwatch")}
                </button>`:l`<span class="kv-value">${e.t("common.unknown")}</span>`})}
        <details
          id="overview-alarms-drawer"
          class="sub-collapsible summary-row"
          ?open=${e.overviewAlarmsOpen}
          @toggle=${P=>{e.overviewAlarmsOpen=P.currentTarget.open}}
        >
          <summary>
            <span class="row-label">${e.t("dev_overview.alarms_label")}</span>
            <span class="summary-row-end">
              <span id="overview-alarms-chip" class=${N}>
                ${E}
              </span>
              <span class="summary-chevron" aria-hidden="true">▾</span>
            </span>
          </summary>
          <div id="overview-alarms" class="card-content stack">
            <p class="row-description">${e.t("dev_overview.alarms_desc")}</p>
            <div
              class="stack"
              role="group"
              aria-label=${e.t("dev_overview.alarms_group_aria")}
            >
              ${[0,1,2].map(P=>{let H=u[P],C=`cfg-alarm_${P+1}_time`,L=`cfg-alarm_${P+1}_recurrence`,D=`cfg-alarm_${P+1}_enabled`;return l`<div class="list-row">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for=${C}>
                        ${e.t("dev_overview.alarm_time_label",{index:P+1})}
                      </label>
                      <input
                        type="time"
                        id=${C}
                        step="60"
                        .value=${S(H.time)}
                        @change=${z=>{let Z=z.currentTarget.value;Z&&p(P,{time:Z.slice(0,5)},C)}}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for=${L}>
                        ${e.t("dev_overview.alarm_schedule_label",{index:P+1})}
                      </label>
                      <select
                        id=${L}
                        .value=${S(String(H.recurrence))}
                        @change=${z=>p(P,{recurrence:Number(z.currentTarget.value)},L)}
                      >
                        ${$.map(z=>l`<option
                              value=${String(z.value)}
                              .selected=${S(z.value===H.recurrence)}
                            >
                              ${z.label}
                            </option>`)}
                      </select>
                    </div>
                  </div>
                  <label for=${D} class="inline-switch">
                    <span>${e.t("common.enabled")}</span>
                    <input
                      type="checkbox"
                      id=${D}
                      .checked=${S(H.enabled)}
                      @change=${z=>p(P,{enabled:z.currentTarget.checked},D)}
                      role="switch"
                      class="switch"
                    />
                  </label>
                </div>`})}
            </div>
          </div>
        </details>
      </div>`})}function wt(e){let t=e.state,o=t?.config||{},i=t?.live||{},a=t?.links||{},n=o.kind==="ble_tag",s=(t?.system_devices||[]).find(b=>b.subentry_id===e.activeSubentryId)||(t?.system_devices||[]).find(b=>b.is_current),r=!n&&s?.is_online===!1,c=(s?.ble_survey_rows||[]).find(b=>b.is_winner),u=(t?.issues||[]).filter(b=>b.subentry_id&&b.subentry_id===e.activeSubentryId),p=u.some(b=>b.severity==="error"||b.severity==="critical"),d=n?i.ble_transmitter_status:null,m=String(d?.state||"").trim(),g=!!d&&!!m&&m.toLowerCase()!=="transmitting",_=!!(a.esphome_device_id||a.latter_device_id),h=e.entity.getSectionItems("other");return l`<section id="view-dashboard" class="stack">
    ${Pe(e)}

    ${u.length?l`<div
          role="region"
          aria-label=${e.t("status.needs_attention")}
          class="alert ${p?"alert-error":"alert-warning"}"
        >
          <div class="alert-body">
            <strong>${e.t("status.needs_attention")}</strong>
            <ul class="alert-list">
              ${u.map(b=>l`<li>${di(b,e.hass)}</li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${()=>e.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("action.open_repairs")}
          </button>
        </div>`:v}

    ${g?l`<div
          id="ble-transmitter-off-banner"
          role="region"
          aria-label=${e.t("offline.ble_tx_off_title",{state:m})}
          class="alert alert-warning"
        >
          <div class="alert-body">
            <strong>${e.t("offline.ble_tx_off_title",{state:m})}</strong>
            <span>${e.t("offline.ble_tx_off_body")}</span>
          </div>
        </div>`:v}

    <div class="columns">
      <div class="column">
        ${Vl(e,{curDevEntry:s,winRow:c,isBleOnly:n,hasOpenInHa:_})}
        ${Fl(e,{isBleOnly:n,isOffline:r,hasOpenInHa:_})}
      </div>

      <div class="column">
        ${Ul(e,{curDevEntry:s,isBleOnly:n})}
        ${zl(e,{isBleOnly:n,isOffline:r})}
        ${h.length?U({title:e.t("card.sensors_controls"),contentClass:"settings-list",body:h.map(b=>Ce(e,b))}):v}
      </div>
    </div>
  </section>`}var gn=new Set(["screensaver_mode","screensaver_style","docked_idle_timeout","screensaver_photo_clock"]),Kl=new Set(["do_not_disturb","bedtime_active","bedtime_display","bedtime_brightness","bedtime_schedule","bedtime_start_hour","bedtime_end_hour","bedtime_mode"]);function Wl(e){let t=e.entity.getPrefs(["tap_to_wake","pickup_to_wake","battery_screen_timeout","battery_hibernate_timeout"]).filter(p=>!gn.has(p.key)),o=e.entity.getPrefs(["do_not_disturb","bedtime_active","bedtime_display","bedtime_brightness","bedtime_schedule","bedtime_start_hour","bedtime_end_hour"]),i=!!o.find(p=>p.key==="bedtime_schedule")?.value,a=o.filter(p=>i||p.key!=="bedtime_start_hour"&&p.key!=="bedtime_end_hour"),n=new Set(t.map(p=>p.key)),s=e.entity.getSectionItems("sleep").filter(p=>{if(p.pref_key)return!1;let d=p.key||p.entity_id&&p.entity_id.split(".").pop()||"";return!(gn.has(d)||Array.from(gn).some(m=>d.endsWith(m))||Kl.has(d)||Array.from(Kl).some(m=>d.endsWith(m))||n.has(d)||Array.from(n).some(m=>d.endsWith(m)))}),r=e.entity.getSectionItems("battery"),c=[...t,...s],u=!c.length&&!a.length&&!r.length;return l`<section id="view-power">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${c.length?l`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">${e.t("dev_power.card_sleep_wake")}</h3>
              </div>
              <div class="card-content settings-list">
                ${t.map(p=>pe(e,p))}
                ${s.map(p=>Ce(e,p))}
              </div>
            </div>`:u?U({title:e.t("dev_power.card_power_battery"),body:l`<p class="empty-state">${e.t("dev_power.empty")}</p>`}):v}
      </div>
      <div class="column">
        ${a.length?U({id:"card-bedtime-mode",title:e.t("dev_power.card_bedtime"),subtitle:e.t("dev_power.card_bedtime_subtitle"),contentClass:"settings-list",body:l`${a.map(p=>pe(e,p))}`}):v}
        ${r.length?l`<div class="card" data-entity-card>
              <div class="card-header">
                <h3 class="card-title">${e.t("dev_power.card_power_battery")}</h3>
              </div>
              <div class="card-content settings-list">
                ${r.map(p=>Ce(e,p))}
              </div>
            </div>`:v}
      </div>
    </div>
  </section>`}function jl(e){let t=e.state,o=t?.config||{},i=o.kind==="ble_tag",a=i||!!o.native_ble_tracking,n=t?.live?.ble_detected_ref_power,s=n!=null&&Number.isFinite(Number(n)),r=s?e.t("dev_presence.ref_power_placeholder_detected",{dbm:A(Number(n),e.hass,0)}):e.t("common.auto"),c=o.ble_ref_power!==null&&o.ble_ref_power!==void 0?String(o.ble_ref_power):"",u=i?t?.live?.ble_transmitter_status:null,p=String(u?.tx_power||"").trim(),d=String(u?.advertise_mode||"").trim(),m=p.toLowerCase().replace(/[^a-z]/g,""),g=d.toLowerCase().replace(/[^a-z]/g,""),_=!!u&&(m==="ultralow"||m==="low"||g==="lowpower"),h=e.entity.getPref("ble_beacon_mode"),b=e.entity.getSectionItems("area").filter(y=>!y.pref_key&&y.key!=="ble_beacon_mode");return l`<section id="view-presence">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${U({title:e.t("dev_presence.card_area_tracking"),contentClass:"settings-list",body:l`${i?v:j({id:"cfg-native_ble_tracking",label:e.t("dev_presence.track_ble_label"),description:e.t("dev_presence.track_ble_desc"),checked:!!o.native_ble_tracking,onChange:y=>e.entity.stageDeviceSetting("native_ble_tracking",y,"cfg-native_ble_tracking")})}
            ${a?l`${i?v:j({id:"cfg-ble_auto_switch",label:e.tPrefLabel("ble_auto_switch"),description:e.t("dev_presence.auto_switch_desc"),checked:!!o.ble_auto_switch,onChange:y=>e.entity.stageDeviceSetting("ble_auto_switch",y,"cfg-ble_auto_switch")})}
                  ${se({id:"cfg-default_area",label:e.t("dev_presence.fallback_area_label"),description:e.t("dev_presence.fallback_area_desc"),value:o.default_area,choices:t?.catalog?.areas,emptyOptionLabel:e.t("dev_presence.fallback_area_auto"),onChange:y=>e.entity.stageDeviceSetting("default_area",y,"cfg-default_area")})}
                  ${h?pe(e,h):v}
                  ${b.map(y=>Ce(e,y))}`:se({id:"cfg-default_area",label:e.t("dev_presence.assigned_area_label"),description:e.t("dev_presence.assigned_area_desc"),value:o.default_area,choices:t?.catalog?.areas,emptyOptionLabel:e.t("dev_overview.unassigned_option"),onChange:y=>e.entity.stageDeviceSetting("default_area",y,"cfg-default_area")})}`})}
      </div>

      <div class="column">
        ${a?U({id:"card-ble-identity",handoffActive:e.isHandoffTarget("card-ble-identity"),title:e.t("dev_presence.card_ble_identity"),contentClass:"stack",body:l`<div class="stacked-field">
                  <label for="cfg-ble_target_address">
                    ${e.t("dev_presence.target_addr_label")}
                  </label>
                  <input
                    type="text"
                    id="cfg-ble_target_address"
                    placeholder=${e.t("dev_presence.target_addr_placeholder")}
                    .value=${V(String(o.ble_target_address||""))}
                    @change=${y=>e.entity.stageDeviceSetting("ble_target_address",y.currentTarget.value.trim(),"cfg-ble_target_address")}
                  />
                  <span class="help-text">${e.t("dev_presence.target_addr_help")}</span>
                </div>
                <div class="stacked-field">
                  <label for="cfg-ble_ref_power">
                    ${e.t("dev_presence.ref_power_label")}
                  </label>
                  <input
                    type="number"
                    id="cfg-ble_ref_power"
                    min="-90"
                    max="-30"
                    step="1"
                    placeholder=${r}
                    .value=${V(c)}
                    @change=${y=>{let f=y.currentTarget.value.trim();if(f===""){e.entity.stageDeviceSetting("ble_ref_power",null,"cfg-ble_ref_power");return}let k=Number(f);Number.isFinite(k)&&e.entity.stageDeviceSetting("ble_ref_power",Math.round(k),"cfg-ble_ref_power")}}
                  />
                  <span class="help-text">${e.t("dev_presence.ref_power_help")}</span>
                </div>
                ${_?l`<div id="ble-companion-power-tip" class="alert">
                      <div class="alert-body">
                        <strong>${e.t("dev_presence.companion_low_title")}</strong>
                        <span>
                          ${e.t("dev_presence.companion_low_body",{txPower:p||e.t("dev_presence.companion_default_power"),modeSuffix:d?e.t("dev_presence.companion_mode_suffix",{mode:d}):"",refSuffix:s?e.t("dev_presence.companion_ref_suffix",{dbm:A(Number(n),e.hass,0)}):""})}
                        </span>
                      </div>
                    </div>`:v}
                ${i?v:l`<div class="stacked-field">
                      <label for="cfg-ble_beacon_uuid">
                        ${e.t("dev_presence.ibeacon_uuid_label")}
                      </label>
                      <input
                        type="text"
                        id="cfg-ble_beacon_uuid"
                        placeholder=${e.t("dev_presence.ibeacon_uuid_placeholder")}
                        .value=${V(String(o.ble_beacon_uuid||""))}
                        @change=${y=>e.entity.stageDeviceSetting("ble_beacon_uuid",y.currentTarget.value.trim(),"cfg-ble_beacon_uuid")}
                      />
                    </div>`}`}):v}
      </div>
    </div>
  </section>`}var Ui=new Set(["update","button","switch","select","number"]);function _n(e){let t=String(e??"").trim();return t!==""&&t!=="unknown"&&t!=="unavailable"}var Yl=new Set(["rpc_outbox","hardware_manifest","link_report"]);function tu(e){return e.key&&Yl.has(e.key)?!0:Array.from(Yl).some(t=>e.entity_id.endsWith(`_${t}`))}var Zl=new Set(["wifi_signal","ip_address","mac_address","firmware_version","latter_sdk","sdk_rev"]);function ou(e){return e.key&&Zl.has(e.key)?!0:Array.from(Zl).some(t=>e.entity_id.endsWith(`_${t}`))}function Fi(e){if(!Number.isFinite(e)||e<0)return"\u2014";let t=Math.round(e);if(t<60)return`${t}s`;let o=Math.floor(t/60);if(o<60){let s=t%60;return s>0?`${o}m ${s}s`:`${o}m`}let i=Math.floor(o/60);if(i<24){let s=o%60;return s>0?`${i}h ${s}m`:`${i}h`}let a=Math.floor(i/24),n=i%24;return n>0?`${a}d ${n}h`:`${a}d`}function iu(e,t,o){if(!_n(e))return[];let i=new Map;for(let m of e.trim().split(/\s+/)){let g=m.indexOf("=");g>0&&g<m.length-1&&i.set(m.slice(0,g),m.slice(g+1))}if(!i.size)return[];let a=[],n=i.get("up");n!==void 0&&Number.isFinite(Number(n))&&a.push({label:B("dev_tools.telem_uptime",void 0,o),value:Fi(Number(n))});let s=i.get("rst");s&&a.push({label:B("dev_tools.telem_last_reset",void 0,o),value:s,code:!0});let r=i.get("disc");if(r!==void 0&&Number.isFinite(Number(r))){let m=Number(i.get("bto")??0),g=Number.isFinite(m)&&m>0?B("dev_tools.telem_beacon_timeouts",{count:A(m,t,0)},o):"";a.push({label:B("dev_tools.telem_wifi_disc",void 0,o),value:`${A(Number(r),t,0)}${g}`})}let c=i.get("rssi");if(c&&c!=="na"&&c.includes("/")){let[m,g]=c.split("/",2);Number.isFinite(Number(m))&&Number.isFinite(Number(g))&&a.push({label:B("dev_tools.telem_wifi_avg_min",void 0,o),value:`${A(Number(m),t,0)} / ${A(Number(g),t,0)} dBm`})}let u=i.get("ha");if(u!==void 0&&Number.isFinite(Number(u))){let m=Number(i.get("gap")??0),g=Number.isFinite(m)&&m>0?B("dev_tools.telem_max_gap",{duration:Fi(m)},o):"";a.push({label:B("dev_tools.telem_ha_sessions",void 0,o),value:`${A(Number(u),t,0)}${g}`})}let p=i.get("slp");if(p!==void 0&&Number.isFinite(Number(p))){let m=Number(i.get("ls")??0),g=Number.isFinite(m)&&m>0?B("dev_tools.telem_cycles",{count:A(m,t,0)},o):"";a.push({label:B("dev_tools.telem_light_sleep",void 0,o),value:`${A(Number(p),t,1)}%${g}`})}let d=i.get("nvs");if(d&&d.includes("/")){let m=d.split("/");m.length>=3&&m.every(g=>Number.isFinite(Number(g)))&&a.push({label:B("dev_tools.telem_nvs_writes",void 0,o),value:B("dev_tools.telem_nvs_value",{writes:A(Number(m[0]),t,0),erases:A(Number(m[1]),t,0),maxMs:A(Number(m[2]),t,0)},o)})}return a}function au(e,t,o){if(!_n(e))return[];let i=e.trim();if(!i.startsWith("{"))return[];let a;try{let d=JSON.parse(i);if(!d||typeof d!="object"||Array.isArray(d))return[];a=d}catch{return[]}let n=[],s=typeof a.board=="string"?a.board.trim():"";s&&n.push({label:B("dev_tools.telem_board",void 0,o),value:s,code:!0});let r=typeof a.chip=="string"?a.chip.trim():"",c=Number(a.psram_mb??0);if(r){let d=Number.isFinite(c)&&c>0?B("dev_tools.telem_psram_suffix",{mb:A(c,t,0)},o):"";n.push({label:B("dev_tools.telem_processor",void 0,o),value:`${r}${d}`})}let u=Number(a.display??0)===1&&a.shape!=="none";if(a.display!==void 0)if(!u)n.push({label:B("dev_tools.telem_display_panel",void 0,o),value:B("dev_tools.telem_headless",void 0,o)});else{let d=Number(a.w??0),m=Number(a.h??0),g=typeof a.shape=="string"?a.shape.trim():"",_=a.ips===1?"IPS":a.ips===0?"AMOLED":"";if(d>0&&m>0){let h=[`${d}\xD7${m}`,g,_].filter(Boolean);n.push({label:B("dev_tools.telem_display_panel",void 0,o),value:h.join(" ")})}}let p=[];return Number(a.touch)===1&&p.push(B("dev_tools.trait_touch",void 0,o)),Number(a.mic)===1&&p.push(B("dev_tools.trait_mic",void 0,o)),Number(a.spk)===1&&p.push(B("dev_tools.trait_speaker",void 0,o)),Number(a.mic)!==1&&Number(a.spk)!==1&&Number(a.audio)===1&&p.push(B("dev_tools.trait_audio",void 0,o)),Number(a.imu)===1&&p.push(B("dev_tools.trait_imu",void 0,o)),Number(a.battery)===1&&p.push(B("dev_tools.trait_battery",void 0,o)),Number(a.wearable)===1&&p.push(B("dev_tools.trait_wearable",void 0,o)),Number(a.stationary)===1&&p.push(B("dev_tools.trait_stationary",void 0,o)),p.length&&n.push({label:B("dev_tools.telem_traits",void 0,o),value:p.join(", ")}),n}function nu(e,t,o,i){if(!e||typeof e!="object")return[];let a=[],n=e.int_ram_free_kb,s=e.int_ram_min_kb,r=e.int_ram_largest_kb;if(n!=null&&Number.isFinite(Number(n))||s!=null&&Number.isFinite(Number(s))||r!=null&&Number.isFinite(Number(r))){let p=d=>d!=null&&Number.isFinite(Number(d))?A(Number(d),o,0):"\u2014";a.push({label:B("dev_tools.telem_int_ram",void 0,i),value:`${p(n)} / ${p(s)} / ${p(r)} KB`})}let c=e.psram_min_kb;c!=null&&Number.isFinite(Number(c))&&Number(c)>0&&a.push({label:B("dev_tools.telem_psram_min",void 0,i),value:`${A(Number(c),o,0)} KB`}),typeof e.ble_active=="boolean"&&a.push({label:B("dev_tools.telem_ble_beacon",void 0,i),value:e.ble_active?B("common.active",void 0,i):B("common.disabled",void 0,i)});let u=e.link;if(t&&u&&typeof u=="object"&&!Array.isArray(u)){let p=u.up_s??u.up;p!=null&&Number.isFinite(Number(p))&&a.push({label:B("dev_tools.telem_uptime",void 0,i),value:Fi(Number(p))});let d=typeof u.rst=="string"?u.rst.trim():"";d&&a.push({label:B("dev_tools.telem_last_reset",void 0,i),value:d,code:!0});let m=u.disc;if(m!=null&&Number.isFinite(Number(m))){let k=Number(u.bto??0),w=Number.isFinite(k)&&k>0?B("dev_tools.telem_beacon_timeouts",{count:A(k,o,0)},i):"";a.push({label:B("dev_tools.telem_wifi_disc",void 0,i),value:`${A(Number(m),o,0)}${w}`})}let g=u.rssi_avg,_=u.rssi_min;g!=null&&_!==void 0&&_!==null&&Number.isFinite(Number(g))&&Number.isFinite(Number(_))&&a.push({label:B("dev_tools.telem_wifi_avg_min",void 0,i),value:`${A(Number(g),o,0)} / ${A(Number(_),o,0)} dBm`});let h=u.ha;if(h!=null&&Number.isFinite(Number(h))){let k=Number(u.gap_s??u.gap??0),w=Number.isFinite(k)&&k>0?B("dev_tools.telem_max_gap",{duration:Fi(k)},i):"";a.push({label:B("dev_tools.telem_ha_sessions",void 0,i),value:`${A(Number(h),o,0)}${w}`})}let b=u.nvs_w,y=u.nvs_e,f=u.nvs_max_ms;b!=null&&Number.isFinite(Number(b))&&Number.isFinite(Number(y??0))&&Number.isFinite(Number(f??0))&&a.push({label:B("dev_tools.telem_nvs_writes",void 0,i),value:B("dev_tools.telem_nvs_value",{writes:A(Number(b),o,0),erases:A(Number(y??0),o,0),maxMs:A(Number(f??0),o,0)},i)})}return a}function Xl(e){let t=e.state,o=t?.config||{},i=t?.live||{},a=t?.links||{},n=t?.esphome,s=o.kind==="ble_tag",r=(t?.system_devices||[]).find(O=>O.subentry_id===e.activeSubentryId)||(t?.system_devices||[]).find(O=>O.is_current),c=!s&&r?.is_online===!1,u=e.entity.getSectionItems("network"),p=e.entity.getSectionItems("developer"),d=u.filter(O=>Ui.has(O.domain)),m=u.filter(O=>!Ui.has(O.domain)&&!tu(O)&&!ou(O)),g=O=>{let re=u.find(K=>K.key===O||K.entity_id.endsWith(`_${O}`));return _n(re?.state)?String(re?.state).trim():""},_=(r?.ble_survey_rows||[]).find(O=>O.is_winner),h=e.t("common.unknown");if(s)_&&_.effective_rssi!==null&&(h=`${A(_.effective_rssi,e.hass,0)} dBm`);else if(r?.wifi_rssi!==null&&r?.wifi_rssi!==void 0)h=`${A(r.wifi_rssi,e.hass,0)} dBm`;else{let O=g("wifi_signal");O&&(h=Number.isFinite(Number(O))?`${A(Number(O),e.hass,0)} dBm`:O)}let b=String(i.device_sw_version||n?.device?.sw_version||g("firmware_version")||"").replace(/^v/i,""),y=b?`v${b}`:e.t("common.unknown"),f=r?.model_label||n?.device?.model||e.t("common.unknown"),k=r?.ip_address||g("ip_address")||"",w=n?.device?.mac||g("mac_address")||"",M=e.entity.getPref("weather_sim_condition"),E=p.filter(O=>Ui.has(O.domain)&&!O.pref_key&&O.key!=="weather_sim_condition"&&O.key!=="telemetry_profiler"&&O.key!=="log_memory_report"&&!O.entity_id.endsWith("_telemetry_profiler")&&!O.entity_id.endsWith("_log_memory_report")),N=p.filter(O=>!Ui.has(O.domain)),$=u.find(O=>O.key==="link_report"||O.entity_id.endsWith("_link_report")),P=u.find(O=>O.key==="hardware_manifest"||O.entity_id.endsWith("_hardware_manifest")),H=iu($?.state,e.hass,e.localeOverlay),C=nu(i.telemetry,H.length===0,e.hass,e.localeOverlay),L=au(P?.state,e.hass,e.localeOverlay),D=!!i.telemetry?.profiler_on,z=!s,Z=String(o.security_pin_policy||"auto"),_e=e.tPrefOption("security_pin_policy",i.effective_security_pin_policy||Z),Q=si.map(O=>({value:O.value,label:e.tPrefOption("security_pin_policy",O.value)})),ee=e.hasConfiguredSecurityPin,oe=!!(a.esphome_device_id||a.latter_device_id);return l`<section id="view-tools">
    ${Pe(e)}

    <div class="columns">
      <div class="column">
        ${U({id:"card-device-diagnostics",handoffActive:e.isHandoffTarget("card-device-diagnostics"),heading:l`<h3 class="card-title">${e.t("card.diagnostics")}</h3>`,contentClass:"stack",body:l`${d.length?l`<div class="settings-list">
                  ${d.map(O=>Ce(e,O))}
                </div>`:v}
            <div class="kv-list">
              ${s?l`<div class="kv-row">
                      <span>${e.t("dev_tools.ble_signal")}</span>
                      <strong>${h}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.ble_target")}</span>
                      <strong>
                        ${o.ble_target_address?l`<code>${o.ble_target_address}</code>`:e.t("common.unknown")}
                      </strong>
                    </div>`:l`<div class="kv-row">
                      <span>${e.t("dev_tools.model")}</span>
                      <strong>${f}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.esphome_node")}</span>
                      <strong>
                        <code id="diag-node-name">
                          ${t?.esphome?.device?.node_name||o.device_slug||e.t("common.unknown")}
                        </code>
                      </strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.firmware_version")}</span>
                      <strong>${y}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.latter_sdk")}</span>
                      <strong id="diag-sdk-rev">
                        ${i.sdk_rev||e.t("common.unknown")}
                      </strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.wifi_signal")}</span>
                      <strong>${h}</strong>
                    </div>
                    <div class="kv-row">
                      <span>${e.t("dev_tools.ip_address")}</span>
                      <strong>
                        ${k?l`<code>${k}</code>`:e.t("common.unknown")}
                      </strong>
                    </div>
                    ${w?l`<div class="kv-row">
                          <span>${e.t("dev_tools.mac_address")}</span>
                          <strong><code>${w}</code></strong>
                        </div>`:v}
                    ${m.map(O=>Ce(e,O))}`}
            </div>
            <div class="settings-list">
              ${a.latter_device_id||a.entry_id?R({id:"row-diagnostics",label:e.t("dev_tools.diagnostics_file_label"),description:e.t("dev_tools.diagnostics_file_desc"),control:l`<button
                      type="button"
                      @click=${()=>{e.tools.downloadDeviceDiagnostics()}}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("action.download_diagnostics")}
                    </button>`}):v}
              ${s?R({label:e.t("dev_tools.backup_row_label"),description:e.t("dev_tools.backup_row_desc"),control:l`<button
                      type="button"
                      @click=${()=>{e.tools.exportBackup(e.activeSubentryId)}}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("action.download_backup")}
                    </button>`}):v}
            </div>
            ${z?l`<details class="sub-collapsible">
                  <summary>${e.t("card.developer_telemetry")}</summary>
                  <div class="card-content">
                    <div class="settings-list">
                      ${M?pe(e,M):v}
                      ${j({id:"dev-telemetry-profiler",label:e.t("dev_tools.profiler_label"),description:e.t("dev_tools.profiler_desc"),disabled:c,checked:D,onChange:O=>{e.entity.runDeviceAction(O?"set_profiler_on":"set_profiler_off")}})}
                      ${R({id:"row-refresh-telemetry",label:e.t("dev_tools.refresh_telemetry_label"),description:e.t("dev_tools.refresh_telemetry_desc"),control:l`<button
                          type="button"
                          id="btn-refresh-telemetry"
                          ?disabled=${c}
                          @click=${()=>{e.entity.runDeviceAction("request_telemetry",e.t("dev_tools.refresh_telemetry_toast"))}}
                          class="btn btn-secondary btn-compact"
                        >
                          ${e.t("action.refresh")}
                        </button>`})}
                      ${E.map(O=>Ce(e,O))}
                    </div>
                    ${N.length||C.length||H.length||L.length?l`<div class="kv-list">
                          ${N.map(O=>Ce(e,O))}
                          ${[...C,...H,...L].map(O=>l`<div class="kv-row">
                              <span>${O.label}</span>
                              <strong>
                                ${O.code?l`<code>${O.value}</code>`:O.value}
                              </strong>
                            </div>`)}
                        </div>`:v}
                  </div>
                </details>`:v}`,footerActions:oe?l`<button
                type="button"
                id="btn-tools-open-in-ha"
                @click=${()=>e.openDeviceInHa(s)}
                class="btn btn-text"
              >
                ${e.t("action.open_in_ha")}
              </button>`:v})}
      </div>

      <div class="column">
        ${s?v:l`${U({id:"card-device-security",title:e.t("card.perimeter_security"),subtitle:e.t("dev_tools.perimeter_subtitle"),contentClass:"settings-list",body:l`${se({id:"cfg-security_pin_policy",label:e.tPrefLabel("security_pin_policy"),description:l`${e.t("dev_tools.pin_policy_desc_prefix")}
                      <strong>${_e}</strong>.`,value:Z,rawOptions:Q,onChange:O=>e.entity.stageDeviceSetting("security_pin_policy",O,"cfg-security_pin_policy")})}
                  ${R({label:e.t("dev_tools.security_pin_label"),description:e.t("dev_tools.security_pin_desc"),stacked:!0,control:l`<div class="input-action-row">
                      <span class="chip ${ee?"chip-success":""}">
                        ${ee?e.t("status.pin_configured"):e.t("status.pin_not_set")}
                      </span>
                      <input
                        type="password"
                        id="dev-security-pin-input"
                        inputmode="numeric"
                        pattern="[0-9]*"
                        autocomplete="new-password"
                        aria-label=${e.t("dev_tools.pin_input_aria")}
                        placeholder=${ee?e.t("dev_tools.pin_placeholder_replace"):e.t("dev_tools.pin_placeholder_new")}
                        .value=${V(e.devicePinDraft)}
                        @input=${O=>{e.devicePinDraft=O.currentTarget.value,e.host.requestUpdate()}}
                      />
                      <button
                        type="button"
                        ?disabled=${e.pinBusy||!e.devicePinDraft.trim()}
                        @click=${()=>{e.tools.saveSecurityPin("device")}}
                        class="btn btn-primary btn-compact"
                      >
                        ${e.t("dev_tools.save_pin")}
                      </button>
                      ${ee?l`<button
                            type="button"
                            ?disabled=${e.pinBusy}
                            @click=${()=>e.tools.requestClearSecurityPin("device")}
                            class="btn btn-danger btn-compact"
                          >
                            ${e.t("dev_tools.clear_pin")}
                          </button>`:v}
                    </div>`})}`})}
              ${U({id:"card-replace-hardware",heading:l`<h3 class="card-title">${e.t("card.replace_hardware")}</h3>`,contentClass:"stack",body:l`<p class="row-description">
                    ${e.t("card.replace_hardware_body")}
                  </p>
                  <div class="input-action-row">
                    <button
                      type="button"
                      id="btn-reconfigure-hardware"
                      @click=${()=>e.openDeviceInHa(!0)}
                      class="btn btn-secondary"
                    >
                      ${e.t("dev_tools.reconfigure_in_ha")}
                    </button>
                    <button
                      type="button"
                      id="btn-download-device-backup"
                      @click=${()=>{e.tools.exportBackup(e.activeSubentryId)}}
                      class="btn btn-text"
                    >
                      ${e.t("action.download_backup")}
                    </button>
                  </div>`})}`}

        ${U({heading:l`<h3 class="card-title">${e.t("card.danger_zone")}</h3>`,danger:!0,contentClass:"settings-list",body:l`${R({label:e.t("dev_tools.reset_defaults_label"),description:e.t("dev_tools.reset_defaults_desc"),control:l`<button
                type="button"
                @click=${()=>e.tools.openResetDeviceModal()}
                class="btn btn-danger"
              >
                ${e.t("dev_tools.reset_defaults_label")}
              </button>`})}
            ${R({label:e.t("dev_tools.remove_device_label"),description:e.t("dev_tools.remove_device_desc"),control:l`<button
                type="button"
                @click=${()=>e.tools.openRemoveDeviceModal(e.activeSubentryId,t?.title||o.device_slug||e.t("devices.col_device"))}
                class="btn btn-danger"
              >
                ${e.t("dev_tools.remove_device_label")}
              </button>`})}`})}
      </div>
    </div>
  </section>`}var su="https://slampton.github.io/esphome-latter-core/",ru="https://github.com/slampton/ha-latter/blob/main/docs/getting-started.md";function Vi(e,t){return t.title||t.target_address||e.t("status.ble_tag")}function lu(e,t,o,i){let a=Vi(e,t),n=Vi(e,o),s=t.target_address||"",r=o.target_address||"";if(i==="rssi"){let u=t.rssi!==null&&t.rssi!==void 0,p=o.rssi!==null&&o.rssi!==void 0;if(u!==p)return u?-1:1;if(u&&p&&t.rssi!==o.rssi)return Number(o.rssi)-Number(t.rssi)}else if(i==="area"){let u=String(t.area_name||"").trim(),p=String(o.area_name||"").trim();if(!!u!=!!p)return u?-1:1;if(u&&p){let d=u.localeCompare(p,void 0,{sensitivity:"base"});if(d!==0)return d}}let c=a.localeCompare(n,void 0,{sensitivity:"base"});return c!==0?c:s.localeCompare(r)}function Jl(e){let t=e.state,o=t?.discovered_latter_devices||[],i=t?.ignored_latter_devices||[],a=!!e.discoveredBlePaused,n=a&&Array.isArray(e.discoveredBleFrozenSnapshot)?e.discoveredBleFrozenSnapshot:t?.discovered_ble_devices||[],s=t?.device_groups||[],r=t?.catalog?.persons||[],c=new Map;for(let b of s)b&&b.id&&c.set(b.id,b.name||te(b.id.replace(/_/g," ")));let u=e.discoveredBleKindFilter||"all",p=e.discoveredBleSort||"name",d=(e.discoveredBleSearch||"").trim().toLowerCase(),m=n.filter(b=>u==="tracker"&&!b.is_tracker||u==="named"&&b.is_tracker?!1:d?[b.title,b.target_address,b.kind,b.area_name].filter(Boolean).join(" ").toLowerCase().includes(d):!0).slice().sort((b,y)=>lu(e,b,y,p)),g=e.discoveredLatterGroupDrafts,_=e.discoveredLatterPersonDrafts,h=e.discoveredBlePersonDrafts;return l`<section id="view-discovered_devices">
    ${U({id:"card-discovered-latter",handoffActive:e.isHandoffTarget("card-discovered-latter"),title:e.t("discovered.latter_devices"),headerActions:l`<button
        type="button"
        @click=${()=>e.openHaPage("/config/integrations/integration/latter")}
        class="btn btn-secondary"
      >
        ${e.t("action.open_integration")}
      </button>`,contentClass:"stack",body:l`<div id="latter-adopt-table-box" class="settings-list">
          ${o.length?ge(o,(b,y)=>`${b.esphome_device_id||b.node_name}::${y}`,b=>{let y=b.title||b.node_name||e.t("discovered.default_latter_title"),f=c.get(b.default_group)||te((b.default_group||"custom").replace(/_/g," ")),k=[b.model_label||e.t("discovered.default_latter_model")];b.node_name&&k.push(e.t("discovered.meta_node",{node:b.node_name})),b.area_name&&k.push(e.t("discovered.meta_area",{area:b.area_name}));let w=g.get(b.esphome_device_id)||"auto",M=_.get(b.esphome_device_id)||"";return R({label:y,description:k.join(" \u2022 "),control:l`<select
                        aria-label=${e.t("discovered.group_select_aria",{title:y})}
                        .value=${S(w)}
                        @change=${E=>{g.set(b.esphome_device_id,E.currentTarget.value||"auto"),e.host.requestUpdate()}}
                      >
                        <option value="auto" .selected=${S(w==="auto")}>
                          ${e.t("discovered.auto_group_option",{group:f})}
                        </option>
                        <option value="custom" .selected=${S(w==="custom")}>
                          ${e.t("common.custom")}
                        </option>
                        ${s.map(E=>l`<option value=${E.id} .selected=${S(w===E.id)}>
                              ${E.name}
                            </option>`)}
                      </select>
                      <select
                        aria-label=${e.t("discovered.person_select_aria",{title:y})}
                        .value=${S(M)}
                        @change=${E=>{_.set(b.esphome_device_id,E.currentTarget.value||""),e.host.requestUpdate()}}
                      >
                        <option value="" .selected=${S(!M)}>
                          ${e.t("common.no_person")}
                        </option>
                        ${r.map(E=>l`<option value=${E.id} .selected=${S(M===E.id)}>
                              ${E.name}
                            </option>`)}
                      </select>
                      <button
                        type="button"
                        @click=${()=>{e.tools.adoptLatterDevice(b.esphome_device_id,y,g.get(b.esphome_device_id)||"auto",_.get(b.esphome_device_id)||"")}}
                        class="btn btn-primary btn-compact"
                      >
                        ${e.t("action.adopt")}
                      </button>
                      <button
                        type="button"
                        aria-label=${e.t("discovered.ignore_aria",{title:y})}
                        @click=${()=>{e.tools.ignoreDiscoveredDevice(b.esphome_device_id,y)}}
                        class="btn btn-text btn-compact"
                      >
                        ${e.t("action.ignore")}
                      </button>`})}):l`<div class="stack">
                <p class="empty-state">${e.t("discovered.empty_latter")}</p>
                <div class="input-action-row">
                  <a
                    href=${su}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="btn btn-secondary btn-compact"
                  >
                    ${e.t("discovered.web_installer")}
                  </a>
                  <a
                    href=${ru}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="btn btn-text btn-compact"
                  >
                    ${e.t("discovered.getting_started")}
                  </a>
                </div>
              </div>`}
        </div>
        ${i.length>0?l`<details
              id="discovered-ignored-drawer"
              class="sub-collapsible summary-row"
              ?open=${e.discoveredIgnoredOpen}
              @toggle=${b=>{e.discoveredIgnoredOpen=b.currentTarget.open}}
            >
              <summary>
                <span class="row-label">
                  ${e.t("discovered.ignored_count",{count:A(i.length,e.hass,0)})}
                </span>
                <span class="summary-row-end">
                  <span class="summary-chevron" aria-hidden="true">▾</span>
                </span>
              </summary>
              <div class="card-content settings-list">
                ${ge(i,(b,y)=>`ignored::${b.esphome_device_id||b.node_name}::${y}`,b=>{let y=b.title||b.node_name||e.t("discovered.default_latter_title"),f=[b.model_label||e.t("discovered.default_latter_model")];return b.node_name&&f.push(e.t("discovered.meta_node",{node:b.node_name})),b.area_name&&f.push(e.t("discovered.meta_area",{area:b.area_name})),R({label:y,description:f.join(" \u2022 "),control:l`<button
                        type="button"
                        aria-label=${e.t("discovered.restore_aria",{title:y})}
                        @click=${()=>{e.tools.unignoreDiscoveredDevice(b.esphome_device_id,y)}}
                        class="btn btn-secondary btn-compact"
                      >
                        ${e.t("action.unignore")}
                      </button>`})})}
              </div>
            </details>`:v}`})}

    ${U({id:"card-discovered-ble",handoffActive:e.isHandoffTarget("card-discovered-ble"),title:e.t("discovered.bluetooth_devices"),headerActions:l`<input
          type="search"
          id="discovered-ble-search"
          aria-label=${e.t("discovered.search_ble_aria")}
          placeholder=${e.t("discovered.search_ble_placeholder")}
          .value=${V(e.discoveredBleSearch)}
          @input=${b=>{e.discoveredBleSearch=b.currentTarget.value,e.host.requestUpdate()}}
        />
        <select
          id="discovered-ble-filter"
          aria-label=${e.t("discovered.filter_ble_aria")}
          .value=${S(u)}
          @change=${b=>{let y=b.currentTarget.value;e.discoveredBleKindFilter=y==="tracker"||y==="named"?y:"all",e.host.requestUpdate()}}
        >
          <option value="all" .selected=${S(u==="all")}>
            ${e.t("discovered.all_ble")}
          </option>
          <option value="tracker" .selected=${S(u==="tracker")}>
            ${e.t("discovered.phones_trackers")}
          </option>
          <option value="named" .selected=${S(u==="named")}>
            ${e.t("discovered.named_ble")}
          </option>
        </select>
        <select
          id="discovered-ble-sort"
          aria-label=${e.t("discovered.sort_ble_aria")}
          .value=${S(p)}
          @change=${b=>{let y=b.currentTarget.value;e.discoveredBleSort=y==="rssi"||y==="area"?y:"name",e.host.requestUpdate()}}
        >
          <option value="name" .selected=${S(p==="name")}>
            ${e.t("discovered.sort_name")}
          </option>
          <option value="rssi" .selected=${S(p==="rssi")}>
            ${e.t("discovered.sort_rssi")}
          </option>
          <option value="area" .selected=${S(p==="area")}>
            ${e.t("discovered.sort_area")}
          </option>
        </select>
        <button
          type="button"
          id="btn-pause-discovered-ble"
          aria-pressed=${String(a)}
          @click=${()=>e.toggleDiscoveredBlePause()}
          class="btn btn-secondary"
        >
          ${a?e.t("discovered.resume_list"):e.t("discovered.pause_list")}
        </button>
        <button
          type="button"
          @click=${()=>e.tools.openAddBleModal()}
          class="btn btn-primary"
        >
          ${e.t("action.add_ble_tag")}
        </button>`,contentClass:"settings-list",body:l`<div id="ble-adopt-table-box" class="settings-list">
        ${a?l`<p class="help-text">
              ${e.t("discovered.paused_hint",{count:A(m.length,e.hass,0)})}
            </p>`:v}
        ${m.length?ge(m,(b,y)=>`${(b.target_address||Vi(e,b)).toLowerCase()}::${y}`,b=>{let y=Vi(e,b),f=b.target_address||"",k=(f||y).toLowerCase(),w=h.get(k)||"",M=b.kind||e.t("discovered.default_ble_kind"),E=!!f&&!M.toLowerCase().includes(f.toLowerCase()),N=[M,...E?[f]:[]];return b.rssi!==null&&b.rssi!==void 0&&N.push(`${A(b.rssi,e.hass,0)} dBm`),b.area_name&&N.push(e.t("discovered.meta_nearest_area",{area:b.area_name})),R({label:y,description:N.join(" \u2022 "),control:l`<select
                      aria-label=${e.t("discovered.person_select_aria",{title:y})}
                      .value=${S(w)}
                      @change=${$=>{h.set(k,$.currentTarget.value||""),e.host.requestUpdate()}}
                    >
                      <option value="" .selected=${S(!w)}>
                        ${e.t("common.no_person")}
                      </option>
                      ${r.map($=>l`<option value=${$.id} .selected=${S(w===$.id)}>
                            ${$.name}
                          </option>`)}
                    </select>
                    <button
                      type="button"
                      @click=${()=>{e.tools.quickAdoptBleCandidate(y,f,h.get(k)||"")}}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("action.adopt")}
                    </button>`})}):l`<p class="empty-state">
              ${n.length?e.t("discovered.empty_ble_filtered"):e.t("discovered.empty_ble_none")}
            </p>`}
      </div>`})}
  </section>`}function Vo(e){if(e.status_code)return e.status_code;let t=String(e.status_label||"").trim().toLowerCase();return t.includes("update")?"update":t==="away"?"away":t==="scanning"?"scanning":t==="online"||e.is_online?"online":"offline"}function Ql(e){return e==="update"?1:e==="offline"||e==="away"||e==="scanning"?2:3}function cu(e,t,o){switch(o){case"online":return e.t("status.online");case"update":return e.t("status.update");case"away":return e.t("status.away");case"scanning":return e.t("status.scanning");case"offline":return t.status_label&&t.status_label.toLowerCase()==="sleeping"?e.t("status.sleeping"):e.t("status.offline");default:return t.status_label||e.t("common.unknown")}}function ec(e){let t=e.state?.system_devices||[],o=e.state?.device_groups||[],i=e.deviceCategoryFilter||"all",a=t.some(h=>h.kind==="ble_tag"&&h.ble_category==="phone"),n=t.some(h=>h.kind==="ble_tag"&&h.ble_category!=="phone"),s=t.some(h=>!!h.assigned_person),r=t.some(h=>Vo(h)==="update"),c=t.some(h=>h.kind!=="ble_tag"&&(!h.device_group||h.device_group==="custom")),u={id:"all",label:e.t("devices.all")},p=[u,{id:"online",label:e.t("devices.online")},{id:"roaming",label:e.t("devices.roaming")},{id:"stationary",label:e.t("devices.stationary")}];i==="native"&&p.push({id:"native",label:e.t("devices.latter_displays")}),i==="ble_tracked"&&p.push({id:"ble_tracked",label:e.t("devices.ble_tracked")}),(a||i==="phone")&&p.push({id:"phone",label:e.t("devices.phones")}),(n||i==="ble_tag")&&p.push({id:"ble_tag",label:e.t("devices.ble_tags")}),(s||i==="assigned_person")&&p.push({id:"assigned_person",label:e.t("devices.assigned_person")}),(r||i==="updates")&&p.push({id:"updates",label:e.t("devices.updates_available")});for(let h of o){if(!h||!h.id||h.id==="custom")continue;let b=`group:${h.id}`;(t.some(f=>f.kind!=="ble_tag"&&f.device_group===h.id)||i===b)&&p.push({id:b,label:e.t("devices.group_prefix",{name:te(h.name)})})}(c||i==="group:custom")&&p.push({id:"group:custom",label:e.t("devices.group_prefix",{name:e.t("common.custom")})});let d=p.find(h=>h.id===i)??u,m=d.id,g=m==="all"?e.t("devices.inventory_heading"):d.label,_=t.filter(h=>{let b=h.kind==="ble_tag",y=b||!!h.is_roaming;return m==="online"?!!h.is_online:m==="native"?!!h.is_latter_native:m==="ble_tracked"?!!h.ble_tracked:m==="assigned_person"?!!h.assigned_person:m==="roaming"?y:m==="stationary"?!y:m==="phone"?b&&h.ble_category==="phone":m==="ble_tag"?b&&h.ble_category!=="phone":m==="updates"?Vo(h)==="update":m==="group:custom"?!b&&(!h.device_group||h.device_group==="custom"):m.startsWith("group:")?!b&&h.device_group===m.slice(6):!0});return _.sort((h,b)=>{let y=0;return e.deviceSortField==="status"?(y=Ql(Vo(h))-Ql(Vo(b)),y===0&&(y=(h.title||"").localeCompare(b.title||""))):e.deviceSortField==="model"?y=(h.model_label||"").localeCompare(b.model_label||""):e.deviceSortField==="area"?y=(h.area_label||"").localeCompare(b.area_label||""):e.deviceSortField==="group"?y=(h.device_group_name||"").localeCompare(b.device_group_name||""):y=(h.title||"").localeCompare(b.title||""),e.deviceSortAsc?y:-y}),l`<section id="view-select_device_prompt">
    ${U({title:g,headerActions:t.length?l`<select
            id="device-category-filter"
            aria-label=${e.t("devices.filter_aria")}
            .value=${S(m)}
            @change=${h=>{e.deviceCategoryFilter=h.currentTarget.value||"all",e.host.requestUpdate()}}
          >
            ${p.map(h=>l`<option value=${h.id} .selected=${S(h.id===m)}>${h.label}</option>`)}
          </select>`:v,footerActions:t.length?v:l`<button
              type="button"
              @click=${()=>e.openDiscoveredDevices()}
              class="btn btn-primary"
            >
              ${e.t("devices.open_discovered")}
            </button>
            <button
              type="button"
              @click=${()=>e.tools.openAddBleModal()}
              class="btn btn-secondary"
            >
              ${e.t("action.add_ble_tag")}
            </button>
            <button
              type="button"
              @click=${()=>e.openSystemSection("area_tracking")}
              class="btn btn-text"
            >
              ${e.t("devices.open_area_presence")}
            </button>`,body:_.length?l`<div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  ${jt(e,"title",e.t("devices.col_device"))}
                  ${jt(e,"model",e.t("devices.col_model"))}
                  ${jt(e,"area",e.t("devices.col_area"))}
                  ${jt(e,"group",e.t("devices.col_group"))}
                  ${jt(e,"status",e.t("devices.col_status"))}
                  <th><span class="sort-btn" aria-hidden="true"></span></th>
                </tr>
              </thead>
              <tbody>
                ${ge(_,h=>h.subentry_id,h=>{let b=Vo(h),y=cu(e,h,b),f=b==="update"?"update":b==="online"?"online":"",k=h.kind==="ble_tag"?h.ble_category==="phone"?e.t("devices.phones"):e.t("devices.ble_tags"):h.device_group==="custom"?e.t("common.custom"):h.device_group_name||e.t("common.unknown"),w=`/latter/devices/${encodeURIComponent(h.subentry_id)}`;return l`<tr @click=${$=>{if(!($.defaultPrevented||$.button!==0||$.shiftKey||$.altKey||$.target?.closest?.("a, button, input, select"))&&!(typeof globalThis.getSelection=="function"&&String(globalThis.getSelection()?.toString()||"").trim()!=="")){if($.metaKey||$.ctrlKey){globalThis.open?.(w,"_blank","noopener,noreferrer");return}e.switchSystemDevice(h.subentry_id)}}}>
                      <td class="col-name">
                        <a href=${w} @click=${$=>{$.defaultPrevented||$.button!==0||$.metaKey||$.ctrlKey||$.shiftKey||$.altKey||($.preventDefault(),$.stopPropagation(),e.switchSystemDevice(h.subentry_id))}} @keydown=${$=>{$.key===" "&&!$.metaKey&&!$.ctrlKey&&!$.shiftKey&&!$.altKey&&($.preventDefault(),e.switchSystemDevice(h.subentry_id))}}>${h.title}</a>
                      </td>
                      <td>${h.model_label||e.t("common.unknown")}</td>
                      <td>${h.area_label||e.t("common.unknown")}</td>
                      <td>${k}</td>
                      <td><span class="status-dot ${f}" aria-hidden="true"></span>${y}</td>
                      <td class="col-open" aria-hidden="true">›</td>
                    </tr>`})}
              </tbody>
            </table>
          </div>`:t.length?l`<p class="empty-state">${e.t("devices.empty_filtered")}</p>`:l`<div class="stack">
              <strong>${e.t("devices.empty_zero_title")}</strong>
              <p class="empty-state">${e.t("devices.empty_zero_body")}</p>
            </div>`})}
  </section>`}var tc=[{id:"display",labelKey:"batch.cat_display"},{id:"interface",labelKey:"batch.cat_interface"},{id:"audio",labelKey:"batch.cat_audio"},{id:"power",labelKey:"batch.cat_power"},{id:"presence",labelKey:"batch.cat_presence"},{id:"security",labelKey:"batch.cat_security"}];function oc(e,t){let o=e.groups.filteredControlTargets(t);if(!o.length)return v;let i=e.groups.getEffectiveBatchValue(t),{value:a,mixed:n,staged:s}=i,r=t.pref_key||"",c=r?e.tPrefLabel(r,te(t.name)):te(t.name),u=te(t.section_title||t.section),p=o.length===1?e.t("batch.row_meta_one",{section:u}):e.t("batch.row_meta_many",{section:u,count:A(o.length,e.hass,0)}),d=n?`${p} \u2022 ${e.t("batch.mixed_hint")}`:p,m=t.option_labels||{},g=s?l`<span class="chip chip-primary">${e.t("batch.staged_badge")}</span>`:n?l`<span class="chip chip-warning">${e.t("batch.mixed_badge")}</span>`:v,_;if(t.domain==="select"&&t.options&&t.options.length)_=l`${g}
      <select
        aria-label=${c}
        .value=${S(n&&!s?"__mixed__":a)}
        @change=${b=>{let y=b.currentTarget.value;y!=="__mixed__"&&r&&e.groups.stageBatchSetting(r,y)}}
      >
        ${n&&!s?l`<option value="__mixed__" .selected=${S(!0)} disabled>
              ${e.t("batch.mixed_badge")}
            </option>`:v}
        ${t.options.map(b=>{let y=m[b]||(r?e.tPrefOption(r,b):b);return l`<option
            value=${b}
            .selected=${S(!(n&&!s)&&b===a)}
          >
            ${y}
          </option>`})}
      </select>`;else if(t.domain==="switch")_=l`${g}
      <input
        type="checkbox"
        role="switch"
        aria-label=${c}
        .checked=${S(!n&&a==="on")}
        @change=${b=>{r&&e.groups.stageBatchSetting(r,b.currentTarget.checked)}}
        class="switch"
      />`;else if(t.domain==="number"){let h=t.min??0,b=t.max??100,y=t.step??1,f=Number.isFinite(Number(a))?Number(a):h;_=t.unit===":00"?l`${g}
            ${Ma({ariaLabel:c,value:f,is24h:$e(e.hass).startsWith("24"),hass:e.hass,mixed:n&&!s,mixedLabel:e.t("batch.mixed_badge"),onCommit:k=>{r&&e.groups.stageBatchSetting(r,k)}})}`:l`${g}
            ${Yt({ariaLabel:c,value:f,min:h,max:b,step:y,unit:t.unit,is24h:$e(e.hass).startsWith("24"),hass:e.hass,onCommit:k=>{r&&e.groups.stageBatchSetting(r,k)}})}`}else if(t.domain==="color"){let h=ue(a)?a.toUpperCase():"#3898FF";_=l`${g}
      <input
        type="color"
        aria-label=${c}
        .value=${S(h)}
        @change=${b=>e.groups.stageBatchColor(t,b.currentTarget.value)}
      />
      <span class="chip">${n&&!s?e.t("batch.mixed_badge"):h}</span>`}else if(t.domain==="pills"&&t.options&&t.options.length){let h=e.groups.getEffectiveBatchPillStates(t),b=h.some(k=>k.staged),y=h.some(k=>k.state==="mixed"),f=b?l`<span class="chip chip-primary">${e.t("batch.staged_badge")}</span>`:y?l`<span class="chip chip-warning">${e.t("batch.mixed_badge")}</span>`:v;_=l`<div role="group" aria-label=${c} class="pill-list">
      ${f}
      ${h.map(k=>{let w=k.state==="on",M=k.state==="mixed",E=M?e.t("batch.mixed_pill_suffix",{label:k.label}):k.label;return l`<span class="pill ${w?"enabled":""}">
          <button
            type="button"
            aria-pressed=${M?"mixed":w?"true":"false"}
            @click=${()=>e.groups.stageBatchPillToggle(t,k.token)}
            class="pill-toggle"
          >
            ${E}
          </button>
        </span>`})}
    </div>`}else _=l`${g}
      <span class="chip">${n?e.t("batch.mixed_badge"):a}</span>`;return R({label:c,description:d,stacked:t.domain==="pills",control:_})}function hn(e,t,o,i,a,n,s){if(i<=1){e.groups.applyBatchCopyFromDevice(t,n);return}let c=o.find(u=>u.subentry_id===t)?.title||t;e.openConfirm({kind:"batch_copy_list",title:e.t("batch.confirm_push_list_title",{listLabel:s,target:a}),consequence:e.t("batch.confirm_push_list_body",{listLabel:s,device:c}),confirmLabel:e.t("batch.confirm_push_list_confirm"),danger:!1,blastRadiusCount:i,onConfirm:async()=>{await e.groups.applyBatchCopyFromDevice(t,n)}})}function ic(e,t,o,i){let n=new Set(["all","online","roaming","stationary","group:custom",...t.map(h=>`group:${h.id}`)]).has(e.batchTargetFilter||"all")&&e.batchTargetFilter||"all",s=e.batchCategoryFilter||"all",r=n==="all"?e.t("batch.all_latter_devices"):n==="online"?e.t("batch.online_devices"):n==="roaming"?e.t("batch.roaming_devices"):n==="stationary"?e.t("batch.stationary_devices"):n==="group:custom"?e.t("common.custom"):t.find(h=>`group:${h.id}`===n)?.name||n.replace(/^group:/,""),c=e.groups.matchingBatchDevices(),u=e.batchCopySourceSubentryId||e.activeSubentryId||o[0]?.subentry_id||"",p=e.groups.batchDraftCount,d=e.groups.hasBatchDraft,m=e.groups.previewBatchDetachmentCount(),g=c.length===1?e.t("batch.apply_to_one"):e.t("batch.apply_to_n",{count:A(c.length,e.hass,0)}),_=()=>!o.length||!c.some(h=>h.has_display!==!1)?v:l`<div class="settings-list">
      <div class="subsection-title">${e.t("batch.copy_lists_title")}</div>
      ${R({label:e.t("batch.template_device"),description:e.t("batch.template_device_desc",{target:r}),control:l`<select
          id="batch-copy-source"
          aria-label=${e.t("batch.template_device_aria")}
          .value=${S(u)}
          @change=${h=>{e.batchCopySourceSubentryId=h.currentTarget.value,e.host.requestUpdate()}}
        >
          ${o.map(h=>l`<option value=${h.subentry_id} .selected=${S(h.subentry_id===u)}>
                ${h.title}
              </option>`)}
        </select>`})}
      <div class="input-action-row">
        <button
          type="button"
          @click=${()=>hn(e,u,o,c.length,r,["dock_items"],e.t("card.app_dock"))}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("batch.push_dock")}
        </button>
        <button
          type="button"
          @click=${()=>hn(e,u,o,c.length,r,["pinned_items"],e.t("dialogs.pinned_label"))}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("batch.push_pinned")}
        </button>
        <button
          type="button"
          @click=${()=>hn(e,u,o,c.length,r,["world_clocks"],e.t("dialogs.world_clocks_label"))}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("batch.push_clocks")}
        </button>
      </div>
    </div>`;return U({id:"card-batch-controls",title:e.t("batch.title"),subtitle:e.t("batch.subtitle"),headerActions:l`${d?l`<span class="chip chip-primary">
            ${e.t("batch.staged_count",{count:A(p,e.hass,0)})}
          </span>`:v}
      <select
        id="batch-target-filter"
        aria-label=${e.t("batch.target_filter_aria")}
        .value=${S(n)}
        @change=${h=>e.groups.setBatchTargetFilter(h.currentTarget.value||"all")}
      >
        <option value="all" .selected=${S(n==="all")}>
          ${e.t("batch.all_latter_devices")}
        </option>
        <option value="online" .selected=${S(n==="online")}>
          ${e.t("batch.online_devices")}
        </option>
        <option value="roaming" .selected=${S(n==="roaming")}>
          ${e.t("batch.roaming_devices")}
        </option>
        <option value="stationary" .selected=${S(n==="stationary")}>
          ${e.t("batch.stationary_devices")}
        </option>
        ${t.map(h=>l`<option
              value=${`group:${h.id}`}
              .selected=${S(n===`group:${h.id}`)}
            >
              ${h.name}
            </option>`)}
        <option value="group:custom" .selected=${S(n==="group:custom")}>
          ${e.t("common.custom")}
        </option>
      </select>
      <select
        id="batch-cat-filter"
        aria-label=${e.t("batch.category_filter_aria")}
        .value=${S(s)}
        @change=${h=>{e.batchCategoryFilter=h.currentTarget.value||"all",e.host.requestUpdate()}}
      >
        <option value="all" .selected=${S(s==="all")}>
          ${e.t("batch.all_categories")}
        </option>
        ${tc.map(h=>l`<option value=${h.id} .selected=${S(s===h.id)}>
              ${e.t(h.labelKey)}
            </option>`)}
      </select>`,contentClass:"stack",body:c.length?l`<div class="help-text">
            ${e.t("batch.target_summary",{count:A(c.length,e.hass,0),names:c.map(h=>h.title).join(", ")})}
          </div>

          ${d&&m>0?l`<div role="status" class="alert alert-warning">
                <div class="alert-body">
                  <span>
                    ${m===1?e.t("batch.detachment_note_one"):e.t("batch.detachment_note_many",{count:A(m,e.hass,0)})}
                  </span>
                </div>
              </div>`:v}

          <div id="system-controls-list" class="stack">
            ${s==="all"?tc.map(h=>{let b=i.filter(f=>f.section===h.id).map(f=>oc(e,f)).filter(f=>f!==v),y=h.id==="interface"?_():v;return!b.length&&y===v?v:l`<details
                    ?open=${e.openBatchCategories.has(h.id)}
                    @toggle=${f=>{if(f.target!==f.currentTarget)return;f.currentTarget.open?e.openBatchCategories.add(h.id):e.openBatchCategories.delete(h.id)}}
                    class="sub-collapsible"
                  >
                    <summary>${e.t(h.labelKey)}</summary>
                    <div class="card-content stack">
                      ${b.length?l`<div class="settings-list">${b}</div>`:v}
                      ${y}
                    </div>
                  </details>`}):(()=>{let h=i.filter(y=>y.section===s).map(y=>oc(e,y)).filter(y=>y!==v),b=s==="interface"?_():v;return!h.length&&b===v?l`<p class="empty-state">${e.t("batch.empty_category")}</p>`:l`${h.length?l`<div class="settings-list">${h}</div>`:v}
                  ${b}`})()}
          </div>`:l`<p class="empty-state">
          ${n==="all"?e.t("batch.empty_all"):e.t("batch.empty_target",{target:r})}
        </p>`,footerActions:c.length?l`<button
            type="button"
            id="btn-batch-reset"
            ?disabled=${!d||e.groups.batchBusy}
            @click=${()=>e.groups.resetBatchDraft()}
            class="btn btn-secondary"
          >
            ${e.t("batch.reset_staged")}
          </button>
          <button
            type="button"
            id="btn-batch-apply"
            ?disabled=${!d||e.groups.batchBusy}
            @click=${()=>e.groups.requestApplyBatchDraft()}
            class="btn btn-primary"
          >
            ${g}
          </button>`:v})}function du(e,t){return e.id==="pocket_carry"?{has_display:!0,is_round:!0,has_imu:!0,has_battery:!0,has_ble_beacon:!0,has_voice:!0,has_audio:!0,is_roaming_device:!0,hw_jpeg:!1}:e.id==="handhelds"?{has_display:!0,is_round:!1,has_imu:!0,has_battery:!0,has_ble_beacon:!0,has_voice:!0,has_audio:!0,is_roaming_device:!0,hw_jpeg:t.length>0?t.some(o=>o.hw_jpeg===!0):!0}:e.id==="wearables"?{has_display:!0,is_round:!1,has_imu:!0,has_battery:!0,has_ble_beacon:!0,has_voice:!0,has_audio:!0,is_roaming_device:!0,hw_jpeg:!1}:e.id==="wall_panels"?{has_display:!0,is_round:!1,has_imu:!1,has_battery:!1,has_ble_beacon:!0,has_voice:!0,has_audio:!0,is_roaming_device:!1,hw_jpeg:!0}:t.length>0?{has_display:t.some(o=>o.has_display!==!1),has_battery:t.some(o=>o.has_battery!==!1),has_ble_beacon:t.some(o=>o.has_ble!==!1),is_roaming_device:t.some(o=>o.is_roaming!==!1),hw_jpeg:t.some(o=>o.hw_jpeg===!0)}:{hw_jpeg:!0}}function uu(e,t,o,i,a){let n=e.entity.getPrefSpec(o);if(!n||!me(n,a))return v;let s=n.options||[];if(s.length===0)return v;let r=String(n.default??s[0]),c=typeof i=="string"&&s.includes(i)?i:r,u=e.tPrefLabel(o,n.label);return R({label:u,control:l`<select
      aria-label=${e.t("groups.for_group_aria",{label:u,group:t.name})}
      .value=${S(c)}
      @change=${p=>{e.groups.updateGroupBaseline(t.id,{[o]:p.currentTarget.value})}}
    >
      ${s.map(p=>l`<option value=${p} .selected=${S(p===c)}>
          ${e.tPrefOption(o,p)}
        </option>`)}
    </select>`})}function pu(e,t,o,i,a,n=!0){if(!n)return v;let s=e.entity.getPrefSpec(o);if(s&&!me(s,a))return v;let r=s?!!s.default:!0,c=i!=null?!!i:r,u=e.tPrefLabel(o,s?.label);return j({label:u,ariaLabel:e.t("groups.for_group_aria",{label:u,group:t.name}),checked:c,onChange:p=>{e.groups.updateGroupBaseline(t.id,{[o]:p})}})}function mu(e,t,o,i,a,n){let s=e.entity.getPrefSpec(o);if(s&&!me(s,a))return v;let r=s?.min??n?.min??0,c=s?.max??n?.max??100,u=s?.step??n?.step??1,p=s?.unit??n?.unit??"",d=Number(s?.default??n?.defaultVal??r),m=Number.isFinite(Number(i))?Number(i):d,g=e.tPrefLabel(o,s?.label);return Zt({label:g,ariaLabel:e.t("groups.for_group_aria",{label:g,group:t.name}),value:m,min:r,max:c,step:u,unit:p,is24h:$e(e.hass).startsWith("24"),hass:e.hass,onCommit:_=>{e.groups.updateGroupBaseline(t.id,{[o]:_})}})}function gu(e,t,o,i,a){let n=e.entity.getPrefSpec(o);if(n&&!me(n,a))return v;let s=Number(n?.default??0),r=Number.isFinite(Number(i))?Number(i):s,c=e.tPrefLabel(o,n?.label);return mi({label:c,ariaLabel:e.t("groups.for_group_aria",{label:c,group:t.name}),value:r,is24h:$e(e.hass).startsWith("24"),hass:e.hass,onCommit:u=>{e.groups.updateGroupBaseline(t.id,{[o]:u})}})}function _u(e,t,o,i,a,n,s=!1){let r=i!=null?String(i):n,c=a.some(p=>p.value===r)?r:n,u=e.tPrefLabel(o);return R({label:u,control:l`<select
      aria-label=${e.t("groups.for_group_aria",{label:u,group:t.name})}
      .value=${S(c)}
      @change=${p=>{let d=p.currentTarget.value,m=s?Number(d)||0:d;e.groups.updateGroupBaseline(t.id,{[o]:m})}}
    >
      ${a.map(p=>l`<option value=${p.value} .selected=${S(p.value===c)}>
            ${p.label}
          </option>`)}
    </select>`})}function hu(e,t,o,i,a,n,s,r){let c=a.filter(g=>me(g,r)),u=typeof i=="string"?i:n,p=new Set(u.split(",").map(g=>g.trim()).filter(Boolean)),d=e.tPrefLabel(o),m=g=>{let _=new Set(p);if(_.has(g)){if(_.size<=s){let b=o==="tools_items"?"tool":o==="games_items"?"game":"category";e.showToast(e.t("common.keep_one_enabled",{noun:b}),!0);return}_.delete(g)}else _.add(g);let h=a.map(b=>b.token).filter(b=>_.has(b));e.groups.updateGroupBaseline(t.id,{[o]:h.join(",")})};return R({label:d,stacked:!0,control:l`<div
      role="group"
      aria-label=${e.t("groups.for_group_aria",{label:d,group:t.name})}
      class="pill-list"
    >
      ${c.map(g=>{let _=p.has(g.token);return l`<span class="pill ${_?"enabled":""}">
          <button
            type="button"
            aria-pressed=${_?"true":"false"}
            @click=${()=>m(g.token)}
            class="pill-toggle"
          >
            ${g.label}
          </button>
        </span>`})}
    </div>`})}function ac(e,t,o,i,a,n,s){let c=a.find(u=>u.subentry_id===i)?.title||i;e.openConfirm({kind:"copy_group_baseline",title:e.t("groups.confirm_copy_title",{group:t.name}),consequence:s?e.t("groups.confirm_copy_list_body",{listLabel:s,device:c,group:t.name}):e.t("groups.confirm_copy_body",{group:t.name,device:c}),confirmLabel:e.t("groups.confirm_copy_confirm"),danger:!1,blastRadiusCount:o>0?o:null,onConfirm:async()=>{await e.groups.copyDeviceToGroupBaseline(t.id,i,n)}})}function nc(e,t,o){let i=String(e||""),a=String(t||""),n=String(o||"");return i==="collection"&&n?`collection:${n}`:i==="single"&&a?`single:${a}`:!i&&a?`single:${a}`:"off"}function vu(e,t,o){let i=t.id,a=t.device_config||{},{caps:n}=o,s=String(a.auto_brightness_mode||"Sun Synchronized"),r=String(a.wake_word_mode||"Docked Only"),c=!!a.native_ble_tracking,u=a.ble_auto_switch!==void 0?!!a.ble_auto_switch:c,p=!!a.sync_device_area,d=!!a.area_handoff,m=String(a.security_pin_policy||"auto"),g=String(a.screensaver_mode??"Docked Only");return l`<details class="sub-collapsible" open>
      <summary>${e.t("groups.section_power_brightness")}</summary>
      <div class="card-content settings-list">
        ${o.renderSpecSelect("tap_to_wake",a.tap_to_wake)}
        ${o.renderSpecSelect("pickup_to_wake",a.pickup_to_wake)}
        ${o.renderSpecSelect("battery_screen_timeout",a.battery_screen_timeout)}
        ${o.renderSpecSelect("battery_hibernate_timeout",a.battery_hibernate_timeout)}
        ${o.renderSpecSelect("screensaver_mode",a.screensaver_mode)}
        ${n.has_battery!==!1||g!=="Never"?o.renderSpecSelect("docked_idle_timeout",a.docked_idle_timeout):v}
        ${o.renderSpecSelect("auto_brightness_mode",a.auto_brightness_mode)}
        ${s==="Disabled"?o.renderSpecRange("manual_brightness",a.manual_brightness):l`${o.renderSpecRange("day_brightness",a.day_brightness)}
              ${o.renderSpecRange("night_brightness",a.night_brightness)}`}
        ${s==="Time Schedule"?l`${o.renderSpecHourSelect("day_start_hour",a.day_start_hour)}
              ${o.renderSpecHourSelect("night_start_hour",a.night_start_hour)}`:v}
        ${o.renderSpecSelect("bedtime_display",a.bedtime_display)}
        ${o.renderSpecRange("bedtime_brightness",a.bedtime_brightness)}
        ${o.renderSpecSwitch("bedtime_schedule",a.bedtime_schedule)}
        ${a.bedtime_schedule?l`${o.renderSpecHourSelect("bedtime_start_hour",a.bedtime_start_hour)}
              ${o.renderSpecHourSelect("bedtime_end_hour",a.bedtime_end_hour)}`:v}
      </div>
    </details>

    <details class="sub-collapsible">
      <summary>${e.t("groups.section_audio_voice")}</summary>
      <div class="card-content settings-list">
        ${o.renderSpecSelect("wake_word_mode",a.wake_word_mode)}
        ${r!=="Disabled"?l`${o.renderSpecSelect("ww_sens_okay_nabu",a.ww_sens_okay_nabu)}
              ${o.renderSpecSelect("ww_sens_hey_luna",a.ww_sens_hey_luna)}
              ${o.renderSpecSelect("ww_sens_hey_jarvis",a.ww_sens_hey_jarvis)}
              ${o.renderSpecSelect("ww_sens_hey_mycroft",a.ww_sens_hey_mycroft)}
              ${o.renderSpecSelect("ww_sens_alexa",a.ww_sens_alexa)}`:v}
        ${o.renderSpecSwitch("wake_screen_on_assist",a.wake_screen_on_assist)}
        ${o.renderSpecRange("alert_volume",a.alert_volume)}
        ${o.renderSpecRange("volume_step_size",a.volume_step_size)}
        ${o.renderSpecSwitch("game_sound_effects",a.game_sound_effects)}
        ${c&&n.is_roaming_device!==!1?l`${j({label:e.tPrefLabel("sync_device_area"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("sync_device_area"),group:t.name}),checked:p,onChange:_=>{e.groups.updateGroupBaseline(i,{sync_device_area:_})}})}
              ${p?o.renderSpecRange("area_follow_dwell_s",a.area_follow_dwell_s,{min:3,max:60,step:1,unit:"s",defaultVal:10}):v}`:v}
        ${j({label:e.tPrefLabel("area_handoff"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("area_handoff"),group:t.name}),checked:d,onChange:_=>{e.groups.updateGroupBaseline(i,{area_handoff:_})}})}
      </div>
    </details>

    <details class="sub-collapsible">
      <summary>${e.t("groups.section_presence_security")}</summary>
      <div class="card-content settings-list">
        ${j({label:e.tPrefLabel("native_ble_tracking"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("native_ble_tracking"),group:t.name}),checked:c,onChange:_=>{e.groups.updateGroupBaseline(i,{native_ble_tracking:_})}})}
        ${c?l`${j({label:e.tPrefLabel("ble_auto_switch"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("ble_auto_switch"),group:t.name}),checked:u,onChange:_=>{e.groups.updateGroupBaseline(i,{ble_auto_switch:_})}})}
              ${o.renderSpecSelect("ble_beacon_mode",a.ble_beacon_mode)}`:v}
        ${o.renderLabeledSelect("security_pin_policy",m,si.map(_=>({value:_.value,label:e.tPrefOption("security_pin_policy",_.value)})),"auto")}
      </div>
    </details>`}function bu(e,t,o){if(!t.include_display||o.caps.has_display===!1)return v;let i=t.id,a=t.device_config||{},n=String(a.color_profile||"Steel Blue"),s=typeof a.device_custom_color=="string"?a.device_custom_color:null,r=ue(s)?String(s).toUpperCase():"#3898FF",c=String(a.screensaver_style??"Ambient Clock"),u=e.state?.system_wallpapers||[],p=e.state?.photo_collections||[],d=y=>{let f=y?u.filter(k=>!lt(k)):u;return[{value:"off",label:e.t("groups.pool_off")},{value:`collection:${de}`,label:e.t("groups.pool_all")},{value:`collection:${Ye}`,label:e.t("groups.pool_defaults")},{value:`collection:${Ze}`,label:e.t("groups.pool_uploads")},...p.map(k=>({value:`collection:${k.id}`,label:e.t("groups.pool_collection_prefix",{name:k.name})})),...f.map(k=>({value:`single:${k.id}`,label:e.t("groups.pool_photo_prefix",{name:k.name||k.id})}))]},m=d(!1),g=nc(a.wallpaper_mode,a.wallpaper_source,a.wallpaper_collection),_=d(!0),h=nc(a.screensaver_photo_mode,a.screensaver_photo_source,a.screensaver_photo_collection),b=$o.map(y=>({value:String(y.value),label:y.label}));return l`<details class="sub-collapsible" open>
    <summary>${e.t("groups.section_display")}</summary>
    <div class="card-content settings-list">
      ${R({label:e.t("groups.wallpaper_pool_label"),control:l`<select
          aria-label=${e.t("groups.for_group_aria",{label:e.t("groups.wallpaper_pool_label"),group:t.name})}
          .value=${S(g)}
          @change=${y=>{let f=y.currentTarget.value;f.startsWith("collection:")?e.groups.updateGroupBaseline(i,{wallpaper_mode:"collection",wallpaper_collection:f.slice(11),wallpaper_source:""}):f.startsWith("single:")?e.groups.updateGroupBaseline(i,{wallpaper_mode:"single",wallpaper_source:f.slice(7),wallpaper_collection:""}):e.groups.updateGroupBaseline(i,{wallpaper_mode:"off",wallpaper_source:"",wallpaper_collection:""})}}
        >
          ${m.map(y=>l`<option value=${y.value} .selected=${S(y.value===g)}>
              ${y.label}
            </option>`)}
        </select>`})}
      ${o.renderLabeledSelect("wallpaper_cycle_minutes",a.wallpaper_cycle_minutes,b,"0",!0)}
      ${o.renderSpecSelect("screensaver_style",a.screensaver_style)}
      ${c==="Photo Frame"?l`${R({label:e.t("groups.screensaver_pool_label"),control:l`<select
                aria-label=${e.t("groups.for_group_aria",{label:e.t("groups.screensaver_pool_label"),group:t.name})}
                .value=${S(h)}
                @change=${y=>{let f=y.currentTarget.value;f.startsWith("collection:")?e.groups.updateGroupBaseline(i,{screensaver_photo_mode:"collection",screensaver_photo_collection:f.slice(11),screensaver_photo_source:""}):f.startsWith("single:")?e.groups.updateGroupBaseline(i,{screensaver_photo_mode:"single",screensaver_photo_source:f.slice(7),screensaver_photo_collection:""}):e.groups.updateGroupBaseline(i,{screensaver_photo_mode:"off",screensaver_photo_source:"",screensaver_photo_collection:""})}}
              >
                ${_.map(y=>l`<option
                    value=${y.value}
                    .selected=${S(y.value===h)}
                  >
                    ${y.label}
                  </option>`)}
              </select>`})}
            ${o.renderLabeledSelect("screensaver_cycle_minutes",a.screensaver_cycle_minutes,b,"15",!0)}
            ${j({label:e.tPrefLabel("screensaver_shuffle"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("screensaver_shuffle"),group:t.name}),checked:!!a.screensaver_shuffle,onChange:y=>{e.groups.updateGroupBaseline(i,{screensaver_shuffle:y})}})}
            ${o.renderSpecSwitch("screensaver_photo_clock",a.screensaver_photo_clock)}`:v}
      ${o.renderSpecSelect("color_profile",a.color_profile)}
      ${n==="Custom"?R({label:e.tPrefLabel("device_custom_color"),control:l`<input
                type="color"
                aria-label=${e.t("groups.for_group_aria",{label:e.tPrefLabel("device_custom_color"),group:t.name})}
                .value=${S(r)}
                @change=${y=>{let f=y.currentTarget.value.toUpperCase();ue(f)&&e.groups.updateGroupBaseline(i,{device_custom_color:f})}}
              />
              <span class="chip">${r}</span>`}):v}
      ${o.renderSpecSelect("va_visual_profile",a.va_visual_profile)}
    </div>
  </details>`}function fu(e,t,o){if(!t.include_interface||o.caps.has_display===!1)return v;let i=t.id,a=t.device_config||{},n=ni.map(m=>({value:String(m.value),label:m.label})),s=e.state?.system_config?.remote_groups||[],r=[{value:"area_auto",label:e.t("groups.remote_match_area")},...s.map(m=>({value:`group:${m.id}`,label:e.t("groups.remote_group_prefix",{name:m.name})})),{value:"all",label:e.t("groups.remote_all_system")}],c=Array.isArray(a.dock_items)?a.dock_items.length:fo.length,u=Array.isArray(a.pinned_items)?a.pinned_items.length:0,p=typeof a.world_clocks=="string"?a.world_clocks.trim():"",d=p?p.split(";").filter(Boolean).length:0;return l`<details class="sub-collapsible" open>
    <summary>${e.t("groups.section_interface")}</summary>
    <div class="card-content settings-list">
      ${o.renderSpecSwitch("home_screen_enabled",a.home_screen_enabled)}
      ${o.renderSpecSelect("start_screen",a.start_screen)}
      ${o.renderSpecSelect("time_format",a.time_format)}
      ${o.renderSpecSelect("home_clock_tap_action",a.home_clock_tap_action)}
      ${o.renderSpecSelect("clock_face",a.clock_face)}
      ${o.renderSpecSelect("home_date_tap_action",a.home_date_tap_action)}
      ${o.renderSpecSelect("return_to_home_timeout",a.return_to_home_timeout)}
      ${o.renderSpecSwitch("wake_greeting",a.wake_greeting)}
      ${o.renderSpecSwitch("weather_background",a.weather_background)}
      ${o.renderSpecSwitch("weather_app_background",a.weather_app_background)}
      ${o.renderSpecSwitch("home_sun",a.home_sun)}
      ${o.renderSpecSwitch("home_moon",a.home_moon)}
      ${j({label:e.tPrefLabel("activity_card"),ariaLabel:e.t("groups.for_group_aria",{label:e.tPrefLabel("activity_card"),group:t.name}),checked:a.activity_card!==!1,onChange:m=>{e.groups.updateGroupBaseline(i,{activity_card:m})}})}
      ${o.renderPills("activity_sources",a.activity_sources,ut,pa,0)}
      ${o.renderPills("home_categories",a.home_categories,Et,ha,1)}
      ${o.renderPills("area_categories",a.area_categories,At,ga,1)}
      ${o.renderPills("tools_items",a.tools_items,it,ba,1)}
      ${o.renderPills("games_items",a.games_items,It,ya,1)}
      ${o.renderLabeledSelect("device_remote_group",a.device_remote_group,r,"area_auto")}
      ${o.renderSpecSwitch("show_utc_clock",a.show_utc_clock)}
      ${o.renderLabeledSelect("calendar_lookahead_days",a.calendar_lookahead_days??30,n,"30",!0)}
      ${o.renderSpecSelect("calendar_week_start",a.calendar_week_start)}
      ${o.renderSpecSelect("album_art_style",a.album_art_style)}
      ${o.renderSpecSelect("music_overlay_style",a.music_overlay_style)}
      ${o.renderSpecSelect("music_auto_open",a.music_auto_open)}
      ${o.renderSpecSelect("album_sort_order",a.album_sort_order)}
      ${o.renderSpecSelect("artist_album_sort_order",a.artist_album_sort_order)}
      ${o.renderSpecSelect("podcast_sort_order",a.podcast_sort_order)}
      ${o.renderSpecSelect("camera_default_view",a.camera_default_view)}
      ${o.renderSpecSelect("camera_framing",a.camera_framing)}
      ${o.renderSpecSelect("camera_carousel_interval",a.camera_carousel_interval)}
      ${o.renderSpecSelect("camera_stream_mode",a.camera_stream_mode)}
      ${o.renderSpecSelect("camera_doorbell_popup",a.camera_doorbell_popup)}
      ${o.hasLatterDevices?l`${R({label:e.t("card.app_dock"),description:c===1?e.t("groups.dock_baseline_desc_one"):e.t("groups.dock_baseline_desc_many",{count:A(c,e.hass,0)}),control:l`<button
                type="button"
                @click=${()=>o.requestCopyKeys(["dock_items"],e.t("card.app_dock"))}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("groups.copy_dock")}
              </button>`})}
            ${R({label:e.t("dialogs.pinned_label"),description:u===1?e.t("groups.pinned_baseline_desc_one"):e.t("groups.pinned_baseline_desc_many",{count:A(u,e.hass,0)}),control:l`<button
                type="button"
                @click=${()=>o.requestCopyKeys(["pinned_items"],e.t("dialogs.pinned_label"))}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("groups.copy_pinned")}
              </button>`})}
            ${R({label:e.t("dialogs.world_clocks_label"),description:d===1?e.t("groups.clocks_baseline_desc_one"):e.t("groups.clocks_baseline_desc_many",{count:A(d,e.hass,0)}),control:l`<button
                type="button"
                @click=${()=>o.requestCopyKeys(["world_clocks"],e.t("dialogs.world_clocks_label"))}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("groups.copy_clocks")}
              </button>`})}`:v}
    </div>
  </details>`}function sc(e,t,o,i){let a=t.id,n=du(t,o),s=!!t.include_display,r=!!t.include_interface,c=e.groupCopySourceDrafts.get(a)||e.activeSubentryId||i[0]?.subentry_id||"",u={caps:n,hasLatterDevices:i.length>0,renderSpecSelect:(p,d)=>uu(e,t,p,d,n),renderSpecSwitch:(p,d,m=!0)=>pu(e,t,p,d,n,m),renderSpecRange:(p,d,m)=>mu(e,t,p,d,n,m),renderSpecHourSelect:(p,d)=>gu(e,t,p,d,n),renderLabeledSelect:(p,d,m,g,_=!1)=>_u(e,t,p,d,m,g,_),renderPills:(p,d,m,g,_)=>hu(e,t,p,d,m,g,_,n),requestCopyKeys:(p,d)=>ac(e,t,o.length,c,i,p,d)};return l`<details
    ?open=${e.openGroupIds.has(a)}
    @toggle=${p=>{if(p.target!==p.currentTarget)return;p.currentTarget.open?e.openGroupIds.add(a):e.openGroupIds.delete(a)}}
    class="sub-collapsible"
  >
    <summary>${e.t("groups.baseline_settings")}</summary>
    <div class="card-content stack">
      <div class="settings-list">
        ${j({label:e.t("groups.include_display"),description:e.t("groups.include_display_desc"),ariaLabel:e.t("groups.for_group_aria",{label:e.t("groups.include_display"),group:t.name}),checked:s,onChange:p=>{e.groups.updateGroupScope(a,{include_display:p})}})}
        ${j({label:e.t("groups.include_interface"),description:e.t("groups.include_interface_desc"),ariaLabel:e.t("groups.for_group_aria",{label:e.t("groups.include_interface"),group:t.name}),checked:r,onChange:p=>{e.groups.updateGroupScope(a,{include_interface:p})}})}
      </div>

      ${vu(e,t,u)}
      ${bu(e,t,u)}
      ${fu(e,t,u)}

      ${i.length?l`<div class="settings-list">
            <div class="subsection-title">${e.t("groups.copy_from_device")}</div>
            ${R({label:e.t("groups.source_device"),description:e.t("groups.source_device_desc"),control:l`<select
                  aria-label=${e.t("groups.copy_into_aria",{name:t.name})}
                  .value=${S(c)}
                  @change=${p=>{e.groupCopySourceDrafts.set(a,p.currentTarget.value),e.host.requestUpdate()}}
                >
                  ${i.map(p=>l`<option value=${p.subentry_id} .selected=${S(p.subentry_id===c)}>
                        ${p.title}
                      </option>`)}
                </select>
                <button
                  type="button"
                  @click=${()=>ac(e,t,o.length,c,i)}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("groups.copy_settings")}
                </button>`})}
          </div>`:v}
    </div>
  </details>`}function rc(e){let t=e.state,i=(t?.system_devices||[]).filter(r=>r.kind!=="ble_tag"),a=t?.device_groups||[],n=t?.system_controls||[],s=i.filter(r=>!r.device_group||r.device_group==="custom");return l`<section id="view-system_sync">
    <div class="columns">
      <div class="column">
        ${U({id:"card-device-groups",title:e.t("groups.card_title"),subtitle:e.t("groups.card_subtitle"),headerActions:e.newGroupFormOpen?v:l`<button
                type="button"
                id="btn-open-create-group"
                @click=${()=>e.groups.toggleNewGroupForm(!0)}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("groups.create_group")}
              </button>`,contentClass:"stack",body:l`${e.newGroupFormOpen?l`<div id="create-group-form" class="list-block">
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="new-group-name">${e.t("groups.group_name")}</label>
                      <input
                        type="text"
                        id="new-group-name"
                        placeholder=${e.t("groups.group_name_placeholder")}
                        .value=${V(e.newGroupName)}
                        @input=${r=>{e.newGroupName=r.currentTarget.value}}
                      />
                    </div>
                    <div class="stacked-field">
                      <label for="new-group-desc">
                        ${e.t("groups.description_optional")}
                      </label>
                      <input
                        type="text"
                        id="new-group-desc"
                        placeholder=${e.t("groups.description_placeholder")}
                        .value=${V(e.newGroupDesc)}
                        @input=${r=>{e.newGroupDesc=r.currentTarget.value}}
                      />
                    </div>
                  </div>
                  <div class="pill-list">
                    <span class="pill ${e.newGroupIncludeDisplay?"enabled":""}">
                      <button
                        type="button"
                        aria-pressed=${e.newGroupIncludeDisplay?"true":"false"}
                        @click=${()=>{e.newGroupIncludeDisplay=!e.newGroupIncludeDisplay,e.host.requestUpdate()}}
                        class="pill-toggle"
                      >
                        ${e.t("groups.include_display")}
                      </button>
                    </span>
                    <span class="pill ${e.newGroupIncludeInterface?"enabled":""}">
                      <button
                        type="button"
                        aria-pressed=${e.newGroupIncludeInterface?"true":"false"}
                        @click=${()=>{e.newGroupIncludeInterface=!e.newGroupIncludeInterface,e.host.requestUpdate()}}
                        class="pill-toggle"
                      >
                        ${e.t("groups.include_interface")}
                      </button>
                    </span>
                  </div>
                  <div class="input-action-row">
                    <select
                      id="new-group-source"
                      aria-label=${e.t("groups.copy_from_aria")}
                      .value=${S(e.newGroupSourceSubentryId)}
                      @change=${r=>{e.newGroupSourceSubentryId=r.currentTarget.value}}
                    >
                      <option value="" .selected=${S(!e.newGroupSourceSubentryId)}>
                        ${e.t("groups.start_from_defaults")}
                      </option>
                      ${i.map(r=>l`<option
                            value=${r.subentry_id}
                            .selected=${S(r.subentry_id===e.newGroupSourceSubentryId)}
                          >
                            ${e.t("groups.copy_from_prefix",{title:r.title})}
                          </option>`)}
                    </select>
                    <button
                      type="button"
                      id="btn-cancel-create-group"
                      @click=${()=>e.groups.toggleNewGroupForm(!1)}
                      class="btn btn-secondary"
                    >
                      ${e.t("action.cancel")}
                    </button>
                    <button
                      type="button"
                      id="btn-create-device-group"
                      @click=${()=>{e.groups.createDeviceGroup()}}
                      class="btn btn-primary"
                    >
                      ${e.t("groups.create_group")}
                    </button>
                  </div>
                </div>`:v}

            <div id="device-groups-list" class="stack">
              ${a.length?ge(a,r=>r.id,r=>{let c=i.filter(g=>g.device_group===r.id),u=ts.has(r.id)||!!r.builtin,p=[r.description||"",c.length?e.t("groups.devices_list_meta",{names:c.map(g=>g.title).join(", ")}):e.t("groups.no_devices_assigned")].filter(Boolean),d=`group-box-${r.id}`,m=e.isHandoffTarget(d);return l`<div
                        id=${d}
                        class="area-presence-box${m?" handoff-active":""}"
                      >
                        <div class="area-box-head">
                          <div class="area-box-heading">
                            <h4 class="area-box-title">${r.name}</h4>
                            <span class="chip ${c.length?"chip-primary":""}">
                              ${c.length===1?e.t("groups.members_one"):e.t("groups.members_many",{count:A(c.length,e.hass,0)})}
                            </span>
                            ${r.include_display?l`<span class="chip">
                                  ${e.t("groups.scope_display_chip")}
                                </span>`:v}
                            ${r.include_interface?l`<span class="chip">
                                  ${e.t("groups.scope_interface_chip")}
                                </span>`:v}
                          </div>
                          <div class="area-box-actions">
                            ${c.length?l`<button
                                  type="button"
                                  @click=${()=>e.openDevicesWithCategory(`group:${r.id}`)}
                                  class="btn btn-text btn-compact"
                                >
                                  ${e.t("groups.view_devices")}
                                </button>`:v}
                            ${u?l`<button
                                  type="button"
                                  id="btn-reset-group-${r.id}"
                                  @click=${()=>e.groups.requestResetDeviceGroup(r.id,r.name,c.length)}
                                  class="btn btn-text btn-compact"
                                >
                                  ${e.t("groups.reset_preset")}
                                </button>`:Se(e.t("groups.delete_group_aria",{name:r.name}),()=>e.groups.requestDeleteDeviceGroup(r.id,r.name,c.length))}
                          </div>
                        </div>

                        <div class="area-box-meta">${p.join(" \u2022 ")}</div>

                        ${sc(e,r,c,i)}
                      </div>`}):l`<p class="empty-state">${e.t("groups.empty_groups")}</p>`}

              <div id="group-box-custom" class="area-presence-box">
                <div class="area-box-head">
                  <div class="area-box-heading">
                    <h4 class="area-box-title">${e.t("groups.custom_summary_title")}</h4>
                    <span class="chip ${s.length?"chip-primary":""}">
                      ${s.length===1?e.t("groups.members_one"):e.t("groups.members_many",{count:A(s.length,e.hass,0)})}
                    </span>
                  </div>
                  <div class="area-box-actions">
                    ${s.length>0?l`<button
                          type="button"
                          id="btn-view-custom-devices"
                          @click=${()=>e.openDevicesWithCategory("group:custom")}
                          class="btn btn-text btn-compact"
                        >
                          ${e.t("groups.view_devices")}
                        </button>`:v}
                  </div>
                </div>
                <div class="area-box-meta">${e.t("groups.custom_summary_desc")}</div>
              </div>
            </div>`})}
      </div>

      <div class="column">
        ${ic(e,a,i,n)}
      </div>
    </div>
  </section>`}var yu="M4,6H20V16H4M20,18A2,2 0 0,0 22,16V6C22,4.89 21.1,4 20,4H4C2.89,4 2,4.89 2,6V16A2,2 0 0,0 4,18H0V20H24V18H20Z",wu="M12,6.5A2.5,2.5 0 0,1 14.5,9A2.5,2.5 0 0,1 12,11.5A2.5,2.5 0 0,1 9.5,9A2.5,2.5 0 0,1 12,6.5M12,2A7,7 0 0,1 19,9C19,14.25 12,22 12,22C12,22 5,14.25 5,9A7,7 0 0,1 12,2M12,4A5,5 0 0,0 7,9C7,10 7,12 12,18.71C17,12 17,10 17,9A5,5 0 0,0 12,4Z",lc="M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12C22,10.84 21.79,9.69 21.39,8.61L19.79,10.21C19.93,10.8 20,11.4 20,12A8,8 0 0,1 12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4C12.6,4 13.2,4.07 13.79,4.21L15.4,2.6C14.31,2.21 13.16,2 12,2M19,2A2,2 0 0,0 17,4A2,2 0 0,0 19,6A2,2 0 0,0 21,4A2,2 0 0,0 19,2M12,6A6,6 0 0,0 6,12A6,6 0 0,0 12,18A6,6 0 0,0 18,12H16A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8V6M12,10A2,2 0 0,0 10,12A2,2 0 0,0 12,14A2,2 0 0,0 14,12A2,2 0 0,0 12,10Z",Su="M17,17H7V7H17M21,11V9H19V7C19,5.89 18.1,5 17,5H15V3H13V5H11V3H9V5H7C5.89,5 5,5.89 5,7V9H3V11H5V13H3V15H5V17A2,2 0 0,0 7,19H9V21H11V19H13V21H15V19H17A2,2 0 0,0 19,17V15H21V13H19V11M15,15H9V9H15V15Z";function qi(e){return!e.is_online&&e.kind!=="ble_tag"&&String(e.status_label||"").trim().toLowerCase()==="sleeping"}function ku(e){return!e.is_online&&e.kind==="ble_tag"&&(e.status_code==="away"||String(e.status_label||"").trim().toLowerCase()==="away")}function $u(e){return!e.is_online&&e.kind==="ble_tag"&&(e.status_code==="scanning"||String(e.status_label||"").trim().toLowerCase()==="scanning")}function Cu(e){return e.kind!=="ble_tag"&&!!e.has_battery&&!e.is_charging&&e.battery_level!==null&&e.battery_level!==void 0&&Number.isFinite(Number(e.battery_level))&&Number(e.battery_level)<=20}function cc(e){let t=e.state,o=t?.system_devices||[],i=t?.issues||[],a=t?.discovered_latter_devices||[],n=t?.system_config,s=t?.live?.area_presence_grid||[],r=t?.ble_area_signatures||[],c=o.length,u=o.filter(x=>x.is_online).length,p=o.filter(x=>qi(x)).length,d=o.filter(x=>ku(x)).length,m=o.filter(x=>$u(x)).length,g=Math.max(0,c-u-p-d-m),_=o.filter(x=>Cu(x)).length,h=o.filter(x=>x.kind!=="ble_tag"&&x.has_display).length,b=o.filter(x=>x.kind==="ble_tag"&&x.ble_category==="phone").length,y=o.filter(x=>x.kind==="ble_tag"&&x.ble_category!=="phone").length,f=o.filter(x=>x.kind!=="ble_tag"&&!x.has_display).length,k=o.filter(x=>x.ble_tracked||x.kind==="ble_tag").length,w=o.filter(x=>!!x.assigned_person).length,M=Math.max(o.filter(x=>x.status_code==="update"||x.status_label==="Update available").length,Number(t?.update_check?.available||0)),E=!!(t?.update_check&&t.update_check.checked>0),N=t?.version?`v${String(t.version).replace(/^v/i,"")}`:e.t("common.unknown"),$=Number(t?.ble_proxy_count??0),P=i.some(x=>x.severity==="error"||x.severity==="critical"),H="chip",C="status-dot",L=e.t("sys_overview.no_devices");i.length>0?(H=P?"chip chip-error":"chip chip-warning",C="status-dot update",L=i.length===1?e.t("sys_overview.issues_one"):e.t("sys_overview.issues_many",{count:A(i.length,e.hass,0)})):c>0&&M>0?(H="chip chip-warning",C="status-dot update",L=M===1?e.t("sys_overview.updates_one"):e.t("sys_overview.updates_many",{count:A(M,e.hass,0)})):c>0&&g===c?L=e.t("status.offline"):c>0&&g>0?(H="chip chip-warning",C="status-dot update",L=e.t("sys_overview.offline_count",{count:A(g,e.hass,0)})):c>0&&_>0?(H="chip chip-warning",C="status-dot update",L=e.t("sys_overview.low_battery_count",{count:A(_,e.hass,0)})):c>0&&u===c?(H="chip chip-success",C="status-dot online",L=e.t("sys_overview.all_online")):c>0&&(H="chip chip-success",C="status-dot online",L=e.t("sys_overview.healthy"));let z=`--signal-pct:${c>0?Math.round(u/c*100):0}%`,Z=[];if(c===0)Z.push(e.t("sys_overview.ready_to_onboard"));else{let x=g>0||p>0||d>0||m>0;g>0&&Z.push(e.t("sys_overview.offline_count",{count:A(g,e.hass,0)})),_>0&&Z.push(e.t("sys_overview.low_battery_count",{count:A(_,e.hass,0)})),p>0&&Z.push(e.t("sys_overview.sleeping_count",{count:A(p,e.hass,0)})),d>0&&Z.push(e.t("sys_overview.away_count",{count:A(d,e.hass,0)})),m>0&&Z.push(e.t("sys_overview.scanning_count",{count:A(m,e.hass,0)})),x||(Z.push(h===1?e.t("sys_overview.displays_one"):e.t("sys_overview.displays_many",{count:A(h,e.hass,0)})),b>0&&Z.push(b===1?e.t("sys_overview.phones_one"):e.t("sys_overview.phones_many",{count:A(b,e.hass,0)})),y>0?Z.push(y===1?e.t("sys_overview.ble_tags_one"):e.t("sys_overview.ble_tags_many",{count:A(y,e.hass,0)})):b===0&&f>0&&Z.push(e.t("sys_overview.audio_count",{count:A(f,e.hass,0)})))}let _e=new Map;for(let x of r)x.area_id&&_e.set(x.area_id,x);let Q=new Map;for(let x of s)x.area_id&&Q.set(x.area_id,x);let ee=n?.remote_groups||[],oe=[],O=new Set;for(let x of s)x.area_id&&!O.has(x.area_id)&&(O.add(x.area_id),oe.push(x.area_id));for(let x of r)x.area_id&&!O.has(x.area_id)&&(O.add(x.area_id),oe.push(x.area_id));for(let x of t?.catalog?.areas||[])x.id&&!O.has(x.id)&&(O.add(x.id),oe.push(x.id));let re=oe.map(x=>{let J=Q.get(x),fe=_e.get(x),Ee=(t?.catalog?.areas||[]).find(ie=>ie.id===x),ze=J?.area_name||fe?.area_name||Ee?.name||x,Le=o.filter(ie=>ie.has_assigned_area&&ie.area_id===x).map(ie=>ie.title),Ke=o.filter(ie=>!ie.has_assigned_area&&(ie.is_online||qi(ie))&&ie.area_id===x).map(ie=>ie.title),Y=ee.filter(ie=>ie.area_id===x).reduce((ie,F)=>ie+(F.remotes||[]).filter(Boolean).length,0),le=fe?!!fe.has_ble_proxy:J?.winning_rssi!==null&&J?.winning_rssi!==void 0,ne=!!fe?.has_signature,He=(J?.active_sensors||[]).length,Ie=Math.max((J?.fusion_sensors||[]).length,He),We=!!J?.is_occupied,St=J?.occupant_names||[],Oe=We||Le.length>0||Ke.length>0||ne||le||Y>0||Ie>0;return{areaId:x,areaName:ze,floorLabel:String(J?.floor_name||"").trim(),isOccupied:We,occupants:St,hasBleProxy:le,hasSignature:ne,scannerCount:Number(fe?.scanner_count||0),stationedTitles:Le,roamingHereTitles:Ke,remoteCount:Y,sensorCount:Ie,activeSensorCount:He,isDeployed:Oe}});re.sort((x,J)=>{if(x.isOccupied!==J.isOccupied)return x.isOccupied?-1:1;let fe=x.stationedTitles.length+x.roamingHereTitles.length,Ee=J.stationedTitles.length+J.roamingHereTitles.length;return fe>0!=Ee>0?fe>0?-1:1:x.areaName.localeCompare(J.areaName,void 0,{sensitivity:"base"})});let K=re.length,I=re.filter(x=>x.isOccupied).length,q=re.filter(x=>x.isDeployed),X=q.length>0?q:re.slice(0,6),ae=q.length>0?Math.max(0,K-q.length):Math.max(0,K-X.length),he=o.filter(x=>!x.has_assigned_area&&(x.is_roaming||x.kind==="ble_tag")),ke=he.filter(x=>x.is_online||qi(x)).length,ve=a.slice(0,3).map(x=>x.title||x.node_name).join(", ")+(a.length>3?"\u2026":"");return l`<section id="view-system_overview" class="stack">
    ${i.length?l`<div
          id="sys-issues-banner"
          role="region"
          aria-labelledby="sys-issues-heading"
          class="alert ${P?"alert-error":"alert-warning"}"
        >
          <div class="alert-body">
            <h2 id="sys-issues-heading" class="row-label">
              ${e.t("status.needs_attention")}
            </h2>
            <ul class="alert-list">
              ${i.map(x=>l`<li>
                  <strong>${x.device_title||e.t("shell.title")}:</strong>
                  ${di(x,e.hass)}
                  ${x.subentry_id?l`<button
                        type="button"
                        @click=${()=>{e.switchSystemDevice(String(x.subentry_id))}}
                        class="btn btn-text btn-compact"
                      >
                        ${e.t("sys_overview.open_device")}
                      </button>`:v}
                </li>`)}
            </ul>
          </div>
          <button
            type="button"
            @click=${()=>e.openHaPage("/config/repairs")}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("action.open_repairs")}
          </button>
        </div>`:v}

    ${a.length?l`<div id="sys-discovered-banner" class="alert">
          <div class="alert-body">
            <strong>${e.t("sys_overview.discovered_banner_title")}</strong>
            <p class="row-description">
              ${a.length===1?e.t("sys_overview.discovered_banner_one",{names:ve}):e.t("sys_overview.discovered_banner_many",{count:A(a.length,e.hass,0),names:ve})}
            </p>
          </div>
          <button
            type="button"
            @click=${()=>e.openDiscoveredDevices("card-discovered-latter")}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("sys_overview.open_discovered")}
          </button>
        </div>`:v}

    <div class="columns">
      <div class="column">
        ${U({id:"card-system-status",title:e.t("card.status"),headerActions:l`<span id="sys-status-chip" class=${H}>
            <span class=${C} aria-hidden="true"></span>${L}
          </span>`,contentClass:"stack",body:l`<div class="status-tiles">
            <button
              type="button"
              id="sys-tile-devices"
              @click=${()=>e.openDevicesWithCategory("all")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${we(yu)}
                <span>${e.t("sys_overview.tile_devices")}</span>
              </div>
              <strong class="status-tile-value">
                ${c>0?e.t("sys_overview.online_ratio",{online:A(u,e.hass,0),total:A(c,e.hass,0)}):e.t("sys_overview.zero_devices")}
              </strong>
              <span class="status-tile-meta">${Z.join(" \u2022 ")}</span>
              ${c>0?l`<div class="signal-track" aria-hidden="true">
                    <div
                      class="signal-fill${g>0&&u===0?" low":""}"
                      style=${z}
                    ></div>
                  </div>`:v}
            </button>

            <button
              type="button"
              id="sys-tile-areas"
              @click=${()=>e.openSystemSection("area_tracking")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${we(wu)}
                <span>${e.t("sys_overview.tile_areas")}</span>
              </div>
              <strong class="status-tile-value">
                ${K>0?e.t("sys_overview.occupied_count",{count:A(I,e.hass,0)}):e.t("common.unknown")}
              </strong>
              <span class="status-tile-meta">
                ${K>0?e.t("sys_overview.areas_proxies_meta",{areas:K===1?e.t("sys_overview.areas_one"):e.t("sys_overview.areas_many",{count:A(K,e.hass,0)}),proxies:$===1?e.t("sys_overview.proxies_one"):e.t("sys_overview.proxies_many",{count:A($,e.hass,0)})}):e.t("sys_overview.no_areas")}
              </span>
            </button>

            <button
              type="button"
              id="sys-tile-roaming"
              @click=${()=>e.openDevicesWithCategory(w>0?"assigned_person":k>0?"ble_tracked":"roaming")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${we(lc)}
                <span>${e.t("sys_overview.tile_people_roaming")}</span>
              </div>
              <strong class="status-tile-value">
                ${w===1?e.t("sys_overview.people_assigned_one"):e.t("sys_overview.people_assigned_many",{count:A(w,e.hass,0)})}
              </strong>
              <span class="status-tile-meta">
                ${e.t("sys_overview.ble_tracked_meta",{count:A(k,e.hass,0)})}
              </span>
            </button>

            <button
              type="button"
              id="sys-tile-release"
              @click=${()=>M>0?e.openDevicesWithCategory("updates"):e.openSystemSection("system_tools","card-support-diagnostics")}
              class="status-tile"
            >
              <div class="status-tile-head">
                ${we(Su)}
                <span>${e.t("sys_overview.tile_release")}</span>
              </div>
              <strong class="status-tile-value">${N}</strong>
              <span class="status-tile-meta">
                ${M>0?M===1?e.t("sys_overview.fw_updates_one"):e.t("sys_overview.fw_updates_many",{count:A(M,e.hass,0)}):E?e.t("status.up_to_date"):e.t("common.unknown")}
              </span>
            </button>
          </div>`,footerActions:l`<button
              type="button"
              @click=${()=>e.openHaPage("/config/repairs")}
              class="btn btn-text"
            >
              ${e.t("action.open_repairs")}
            </button>
            <button
              type="button"
              @click=${()=>{e.tools.checkSystemUpdates()}}
              class="btn btn-text"
            >
              ${e.t("sys_overview.check_fw_updates")}
            </button>`})}
      </div>

      <div class="column">
        ${U({id:"card-area-deployment",title:e.t("card.area_deployment"),subtitle:e.t("sys_overview.area_deployment_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.openSystemSection("area_tracking")}
            class="btn btn-text btn-compact"
          >
            ${e.t("sys_overview.manage_presence")}
          </button>`,contentClass:"stack",body:l`${he.length>0?l`<button
                  type="button"
                  id="sys-deploy-roaming"
                  @click=${()=>e.openDevicesWithCategory("roaming")}
                  class="overview-box"
                >
                  <div class="overview-box-head">
                    <span class="overview-box-title">
                      ${we(lc)}
                      <span>${e.t("sys_overview.roaming_devices")}</span>
                    </span>
                    <span class="overview-box-end">
                      <span class="chip ${ke>0?"chip-primary":""}">
                        ${e.t("sys_overview.roaming_active_ratio",{online:A(ke,e.hass,0),total:A(he.length,e.hass,0)})}
                      </span>
                      <span class="overview-box-chevron" aria-hidden="true">›</span>
                    </span>
                  </div>
                  <span class="overview-box-meta">
                    ${he.slice(0,4).map(x=>x.area_id&&x.active_area_name&&(x.is_online||qi(x))?`${x.title} (${x.active_area_name})`:x.title).join(" \u2022 ")}${he.length>4?` \u2022 ${e.t("sys_overview.plus_more",{count:A(he.length-4,e.hass,0)})}`:""}
                  </span>
                </button>`:v}
            ${X.length>0?X.map(x=>{let J=[];x.stationedTitles.length>0&&J.push(x.stationedTitles.join(", ")),x.roamingHereTitles.length>0?J.push(e.t("sys_overview.here_prefix",{names:x.roamingHereTitles.join(", ")})):x.occupants.length>0&&J.push(x.occupants.join(", ")),x.remoteCount>0&&J.push(x.remoteCount===1?e.t("sys_overview.remotes_one"):e.t("sys_overview.remotes_many",{count:A(x.remoteCount,e.hass,0)})),x.activeSensorCount>0?J.push(x.activeSensorCount===1?e.t("sys_overview.active_sensors_one"):e.t("sys_overview.active_sensors_many",{count:A(x.activeSensorCount,e.hass,0)})):x.sensorCount>0&&J.push(x.sensorCount===1?e.t("sys_overview.sensors_one"):e.t("sys_overview.sensors_many",{count:A(x.sensorCount,e.hass,0)})),J.length||J.push(x.isOccupied?e.t("sys_overview.occupied"):e.t("sys_overview.no_devices_stationed"));let fe=!x.hasSignature&&!x.hasBleProxy&&(x.stationedTitles.length>0||x.sensorCount>0);return l`<button
                    type="button"
                    @click=${()=>e.openSystemSection("area_tracking",`area-box-${x.areaId}`)}
                    class="overview-box"
                  >
                    <div class="overview-box-head">
                      <span class="overview-box-title">
                        <span>${x.areaName}</span>
                        ${x.floorLabel?l`<span class="chip">${x.floorLabel}</span>`:v}
                      </span>
                      <span class="overview-box-end">
                        ${x.isOccupied?l`<span class="chip chip-success">
                              ${e.t("sys_overview.occupied")}
                            </span>`:v}
                        ${x.hasSignature?l`<span class="chip chip-primary">
                              ${e.t("sys_overview.signature_count",{count:A(x.scannerCount,e.hass,0)})}
                            </span>`:x.hasBleProxy?l`<span class="chip">${e.t("sys_overview.ble_proxy")}</span>`:l`<span class="chip ${fe?"chip-warning":""}">
                                ${e.t("sys_overview.no_ble_proxy")}
                              </span>`}
                        <span class="overview-box-chevron" aria-hidden="true">›</span>
                      </span>
                    </div>
                    <span class="overview-box-meta">${J.join(" \u2022 ")}</span>
                  </button>`}):he.length===0?l`<p class="empty-state">${e.t("sys_overview.empty_deployment")}</p>`:v}
            ${ae>0?l`<p class="help-text">
                  ${ae===1?e.t("sys_overview.unconfigured_areas_one"):e.t("sys_overview.unconfigured_areas_many",{count:A(ae,e.hass,0)})}
                </p>`:v}`})}
      </div>
    </div>
  </section>`}var Tu="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z",xu="M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z";function dc(e){let t=e.state,o=t?.system_wallpapers||[],i=t?.photo_collections||[],a=new Map(i.map(w=>[w.id,w.name])),n=o.filter(w=>!Ge(w)).length,s=o.filter(w=>Ge(w)).length,r=o.filter(w=>(w.collections||[]).length===0).length,c=e.photosFilterCollection===de||e.photosFilterCollection===Ye||e.photosFilterCollection===Ze||e.photosFilterCollection===mt||i.some(w=>w.id===e.photosFilterCollection)?e.photosFilterCollection:de,u=oo(o,c,e.photosSearch),p=u.length,d=Math.max(1,Math.ceil(p/So)),m=Math.min(Math.max(1,e.photosPage||1),d),g=(m-1)*So,_=u.slice(g,g+So),h=e.photosSelectedIds.size,b=Array.from(e.photosSelectedIds).filter(w=>{let M=o.find(E=>E.id===w);return M?Ge(M):!1}).length,y=w=>{e.photosFilterCollection=w,e.photosPage=1,e.host.requestUpdate()},f=w=>{e.photosSelectedIds.has(w)?e.photosSelectedIds.delete(w):e.photosSelectedIds.add(w),e.host.requestUpdate()},k=[{id:de,label:e.t("photos.filter_all"),count:o.length},{id:Ye,label:e.t("photos.filter_defaults"),count:n},{id:Ze,label:e.t("photos.filter_my_photos"),count:s},{id:mt,label:e.t("photos.filter_uncategorized"),count:r}];return l`<section id="view-photos" class="stack">
    ${U({id:"card-photo-library",handoffActive:e.isHandoffTarget("card-photo-library"),title:e.t("card.photo_library"),subtitle:e.t("photos.subtitle"),headerActions:l`<button
          type="button"
          id="btn-photos-upload"
          @click=${()=>e.entity.openPhotoUploadModal()}
          class="btn btn-primary btn-compact"
        >
          ${e.t("photos.upload_btn")}
        </button>
        <button
          type="button"
          id="btn-photos-import-media"
          @click=${()=>e.entity.openMediaImportModal()}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("photos.import_media_btn")}
        </button>
        <button
          type="button"
          id="btn-photos-new-collection"
          @click=${()=>{e.photosNewCollectionOpen=!e.photosNewCollectionOpen,e.photosNewCollectionOpen||(e.photosNewCollectionName=""),e.host.requestUpdate()}}
          class="btn btn-secondary btn-compact"
        >
          ${e.t("photos.new_collection_btn")}
        </button>`,contentClass:"stack",body:l`${e.photosNewCollectionOpen?l`<div id="photos-new-collection-bar" class="input-action-row">
              <input
                type="text"
                id="input-new-collection-name"
                aria-label=${e.t("photos.new_collection_btn")}
                placeholder=${e.t("photos.new_collection_placeholder")}
                .value=${V(e.photosNewCollectionName)}
                @input=${w=>{e.photosNewCollectionName=w.currentTarget.value}}
                @keydown=${w=>{w.key==="Enter"?(w.preventDefault(),e.entity.createPhotoCollection(e.photosNewCollectionName)):w.key==="Escape"&&(e.photosNewCollectionOpen=!1,e.photosNewCollectionName="",e.host.requestUpdate())}}
              />
              <button
                type="button"
                id="btn-create-collection-submit"
                @click=${()=>{e.entity.createPhotoCollection(e.photosNewCollectionName)}}
                class="btn btn-primary btn-compact"
              >
                ${e.t("photos.create_collection")}
              </button>
              <button
                type="button"
                @click=${()=>{e.photosNewCollectionOpen=!1,e.photosNewCollectionName="",e.host.requestUpdate()}}
                class="btn btn-text btn-compact"
              >
                ${e.t("action.cancel")}
              </button>
            </div>`:v}

        <div id="photos-collection-strip" class="collection-strip" role="group" aria-label=${e.t("photo_edit.collections_label")}>
          ${k.map(w=>{let M=c===w.id;return l`<div class="collection-chip-wrap ${M?"active":""}">
              <button
                type="button"
                data-collection-filter=${w.id}
                aria-pressed=${M?"true":"false"}
                @click=${()=>y(w.id)}
                class="collection-chip-btn"
              >
                <span>${w.label}</span>
                <span>(${A(w.count,e.hass,0)})</span>
              </button>
            </div>`})}

          ${i.map(w=>{let M=c===w.id;return e.photosRenamingCollectionId===w.id?l`<div class="input-action-row">
                <input
                  type="text"
                  id="input-rename-collection"
                  aria-label=${e.t("photos.rename_collection_aria",{name:w.name})}
                  placeholder=${e.t("photos.rename_collection_placeholder")}
                  .value=${V(e.photosRenamingCollectionName)}
                  @input=${N=>{e.photosRenamingCollectionName=N.currentTarget.value}}
                  @keydown=${N=>{N.key==="Enter"?(N.preventDefault(),e.entity.renamePhotoCollection(w.id,e.photosRenamingCollectionName)):N.key==="Escape"&&(e.photosRenamingCollectionId="",e.photosRenamingCollectionName="",e.host.requestUpdate())}}
                />
                <button
                  type="button"
                  @click=${()=>{e.entity.renamePhotoCollection(w.id,e.photosRenamingCollectionName)}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("action.save")}
                </button>
                <button
                  type="button"
                  @click=${()=>{e.photosRenamingCollectionId="",e.photosRenamingCollectionName="",e.host.requestUpdate()}}
                  class="btn btn-text btn-compact"
                >
                  ${e.t("action.cancel")}
                </button>
              </div>`:l`<div class="collection-chip-wrap ${M?"active":""}">
              <button
                type="button"
                data-collection-filter=${w.id}
                aria-pressed=${M?"true":"false"}
                @click=${()=>y(w.id)}
                class="collection-chip-btn"
              >
                <span>${w.name}</span>
                <span>(${A(w.count,e.hass,0)})</span>
              </button>
              <button
                type="button"
                aria-label=${e.t("photos.rename_collection_aria",{name:w.name})}
                @click=${()=>{e.photosRenamingCollectionId=w.id,e.photosRenamingCollectionName=w.name,e.host.requestUpdate()}}
                class="collection-chip-action"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${Tu} /></svg>
              </button>
              <button
                type="button"
                aria-label=${e.t("photos.delete_collection_aria",{name:w.name})}
                @click=${()=>e.entity.requestDeletePhotoCollection(w.id,w.name)}
                class="collection-chip-action"
              >
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${xu} /></svg>
              </button>
            </div>`})}
        </div>

        <div class="photo-toolbar">
          <div class="photo-toolbar-start">
            <input
              type="search"
              id="input-photos-search"
              aria-label=${e.t("photos.search_aria")}
              placeholder=${e.t("photos.search_placeholder")}
              .value=${V(e.photosSearch)}
              @input=${w=>{e.photosSearch=w.currentTarget.value,e.photosPage=1,e.host.requestUpdate()}}
              class="photo-search-input"
            />
          </div>
          <div class="photo-toolbar-end">
            <button
              type="button"
              id="btn-photos-toggle-select"
              @click=${()=>{e.photosSelectMode=!e.photosSelectMode,e.photosSelectMode||e.photosSelectedIds.clear(),e.host.requestUpdate()}}
              class="btn btn-secondary btn-compact"
            >
              ${e.photosSelectMode?e.t("photos.done_selecting_btn"):e.t("photos.select_mode_btn")}
            </button>
          </div>
        </div>

        ${e.photosSelectMode?l`<div id="photos-bulk-bar" class="photo-bulk-bar">
              <div class="photo-toolbar-start">
                <span class="chip chip-primary">
                  ${h===1?e.t("photos.selected_count_one"):e.t("photos.selected_count_many",{count:A(h,e.hass,0)})}
                </span>
                <button
                  type="button"
                  id="btn-photos-select-page"
                  @click=${()=>{for(let w of _)e.photosSelectedIds.add(w.id);e.host.requestUpdate()}}
                  class="btn btn-text btn-compact"
                >
                  ${e.t("photos.select_all_page")}
                </button>
                ${h>0?l`<button
                      type="button"
                      id="btn-photos-clear-selection"
                      @click=${()=>{e.photosSelectedIds.clear(),e.host.requestUpdate()}}
                      class="btn btn-text btn-compact"
                    >
                      ${e.t("photos.clear_selection")}
                    </button>`:v}
              </div>

              <div class="photo-toolbar-end">
                ${i.length>0?l`<select
                        id="select-bulk-collection"
                        aria-label=${e.t("photos.bulk_collection_aria")}
                        .value=${S(e.photosBulkTargetCollectionId)}
                        @change=${w=>{e.photosBulkTargetCollectionId=w.currentTarget.value,e.host.requestUpdate()}}
                      >
                        <option value="" .selected=${S(!e.photosBulkTargetCollectionId)}>
                          ${e.t("photos.bulk_choose_collection")}
                        </option>
                        ${i.map(w=>l`<option
                            value=${w.id}
                            .selected=${S(e.photosBulkTargetCollectionId===w.id)}
                          >
                            ${w.name}
                          </option>`)}
                      </select>
                      <button
                        type="button"
                        id="btn-bulk-add-collection"
                        ?disabled=${h===0||!e.photosBulkTargetCollectionId}
                        @click=${()=>{e.entity.bulkUpdatePhotos({addCollection:e.photosBulkTargetCollectionId})}}
                        class="btn btn-secondary btn-compact"
                      >
                        ${e.t("photos.bulk_add_to_collection")}
                      </button>
                      <button
                        type="button"
                        id="btn-bulk-remove-collection"
                        ?disabled=${h===0||!e.photosBulkTargetCollectionId}
                        @click=${()=>{e.entity.bulkUpdatePhotos({removeCollection:e.photosBulkTargetCollectionId})}}
                        class="btn btn-secondary btn-compact"
                      >
                        ${e.t("photos.bulk_remove_from_collection")}
                      </button>`:v}
                <button
                  type="button"
                  id="btn-bulk-delete-photos"
                  ?disabled=${b===0}
                  @click=${()=>e.entity.requestBulkDeletePhotos()}
                  class="btn btn-danger btn-compact"
                >
                  ${e.t("photos.bulk_delete_btn")}
                </button>
              </div>
            </div>`:v}

        <div id="photos-grid" class="photo-grid">
          ${_.length===0?l`<p class="empty-state">${e.t("photos.empty_library")}</p>`:ge(_,w=>w.id,w=>{let M=e.photosSelectedIds.has(w.id),E=lt(w),N=Ge(w),$=w.thumb_url||w.preview_url||"",P=(w.collections||[]).map(D=>a.get(D)).filter(D=>!!D),H=()=>{e.photosSelectMode?f(w.id):e.entity.openPhotoEditModal(w)},C=E?e.t("photos.badge_dynamic"):N?w.source_kind==="media_import"?e.t("photos.badge_media"):"":e.t("photos.badge_default"),L=e.photosSelectMode?e.t("photos.select_photo_aria",{name:w.name||w.id}):e.t("photos.edit_photo_aria",{name:w.name||w.id});return l`<div
                    data-photo-id=${w.id}
                    class="photo-tile ${M?"selected":""}"
                  >
                    ${e.photosSelectMode?l`<input
                          type="checkbox"
                          aria-label=${e.t("photos.select_photo_aria",{name:w.name||w.id})}
                          .checked=${S(M)}
                          @change=${()=>f(w.id)}
                          class="photo-tile-check"
                        />`:v}
                    <button
                      type="button"
                      aria-label=${C?`${L}, ${C}`:L}
                      @click=${H}
                      class="photo-tile-thumb-btn"
                    >
                      ${$?l`<img
                            src=${$}
                            alt=${w.name||w.id}
                            loading="lazy"
                            class="photo-tile-img"
                          />`:v}
                      ${C?l`<span class="photo-tile-badge">${C}</span>`:v}
                    </button>
                    <div class="photo-tile-meta">
                      <span class="photo-tile-name">${w.name||w.id}</span>
                      ${P.length>0?l`<div class="photo-tile-sub">
                            ${P.slice(0,2).map(D=>l`<span class="chip">${D}</span>`)}
                            ${P.length>2?l`<span class="chip">+${P.length-2}</span>`:v}
                          </div>`:v}
                    </div>
                  </div>`})}
        </div>

        ${p>So?l`<div class="photo-pagination">
              <span class="row-description">
                ${e.t("photos.page_status",{start:A(g+1,e.hass,0),end:A(Math.min(g+_.length,p),e.hass,0),total:A(p,e.hass,0)})}
              </span>
              <div class="photo-toolbar-end">
                <button
                  type="button"
                  id="btn-photos-prev-page"
                  ?disabled=${m<=1}
                  @click=${()=>{e.photosPage=Math.max(1,m-1),e.host.requestUpdate()}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("photos.prev_page")}
                </button>
                <button
                  type="button"
                  id="btn-photos-next-page"
                  ?disabled=${m>=d}
                  @click=${()=>{e.photosPage=Math.min(d,m+1),e.host.requestUpdate()}}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.t("photos.next_page")}
                </button>
              </div>
            </div>`:v}`})}
  </section>`}var Gi=3.28084;function uc(e){let t=e.state,o=t?.system_config,i=String(e.hass?.config?.unit_system?.length||"").toLowerCase(),a=i==="mi"||i==="ft",n=Number(o?.ble_max_radius_m??12),s=a?Math.round(n*Gi*10)/10:n,r=Number(o?.ble_max_velocity_mps??3.5),c=a?Math.round(r*Gi*10)/10:r,u=t?.live?.area_presence_grid||[],p=t?.ble_area_signatures||[],m=(t?.system_devices||[]).filter(C=>C.ble_tracked||C.kind==="ble_tag"),g=e.groups.getActiveSurveyDevice()||m[0],_=g?.ble_survey_rows||[],h=g?.ble_packets_seen??0,b=[{val:"weighted",label:e.t("presence_sys.mode_weighted")},{val:"any_or",label:e.t("presence_sys.mode_any_or")},{val:"ble_only",label:e.t("presence_sys.mode_ble_only")},{val:"ble_and_sensor",label:e.t("presence_sys.mode_both")}],y=new Map;for(let C of p)C.area_id&&y.set(C.area_id,C);let f=new Map;for(let C of u)C.area_id&&f.set(C.area_id,C);let k=[];for(let C of u)k.push({areaId:C.area_id,areaName:C.area_name,row:C,sig:y.get(C.area_id)});for(let C of p)f.has(C.area_id)||k.push({areaId:C.area_id,areaName:C.area_name,row:void 0,sig:C});k.sort((C,L)=>C.areaName.localeCompare(L.areaName,void 0,{sensitivity:"base"}));let w=p.length?p.map(C=>({area_id:C.area_id,area_name:C.area_name})):(t?.catalog?.areas||[]).map(C=>({area_id:C.id,area_name:C.name})),M=e.bleCalibrateAreaId&&w.some(C=>C.area_id===e.bleCalibrateAreaId)?e.bleCalibrateAreaId:w[0]?.area_id||"",E=y.get(M),N=E?.area_name||w.find(C=>C.area_id===M)?.area_name||e.t("presence_sys.this_area"),$=w.length?E?.has_signature?e.t("presence_sys.cal_desc_replace",{count:A(E.scanner_count,e.hass,0),area:N}):E&&!E.has_ble_proxy?e.t("presence_sys.cal_desc_proxyless",{area:N}):e.t("presence_sys.cal_desc_new",{area:N}):e.t("presence_sys.cal_desc_no_areas"),P=_.some(C=>!!C.is_fresh&&C.effective_rssi!==null&&C.effective_rssi!==void 0),H=k.some(({row:C})=>(C?.illuminance_sensor_choices?.length||0)>0);return l`<section id="view-area_tracking">
    <div class="columns">
      <div class="column">
        ${U({id:"card-area-presence",title:e.t("card.area_presence_sensors"),subtitle:e.t("presence_sys.area_card_subtitle"),headerActions:H?l`<button
                type="button"
                ?disabled=${e.groups.isCalibratingIlluminance()}
                class="btn btn-secondary btn-compact"
                @click=${()=>{e.groups.calibrateAreaIlluminance()}}
              >
                ${e.groups.calibratingAllIlluminance?e.t("presence_sys.calibrating_lux"):e.t("presence_sys.calibrate_all_lux")}
              </button>`:v,body:l`<div id="area-presence-grid-box" class="stack">
            ${k.length?ge(k,C=>C.areaId,({areaId:C,areaName:L,row:D,sig:z})=>{let Z=!!D?.is_occupied,Q=D?.confidence_pct!==null&&D?.confidence_pct!==void 0&&Number.isFinite(Number(D.confidence_pct))?li(Number(D?.confidence_pct),e.hass):e.t("common.unknown"),ee=String(D?.floor_name||D?.floor_id||z?.floor_id||"").trim(),oe=z?!!z.has_ble_proxy:!!(D?.winning_rssi!==null&&D?.winning_rssi!==void 0||_.some(Y=>Y.area_id===C)),O=D?.occupant_names||[],K=[O.length?O.join(", "):Z?e.t("presence_sys.occupied_sensor"):e.t("presence_sys.empty")];if(D?.winning_rssi!==null&&D?.winning_rssi!==void 0){let Y=D.closest_distance_m!==null&&D.closest_distance_m!==void 0?` (~${zt(D.closest_distance_m,e.hass,D.closest_distance_ft)})`:"";K.push(e.t("presence_sys.ble_dbm",{rssi:A(D.winning_rssi,e.hass,0),distance:Y}))}D?.match_method==="signature"&&K.push(e.t("presence_sys.signature_match")),D?.active_sensors&&D.active_sensors.length?K.push(D.active_sensors.length===1?e.t("presence_sys.active_sensors_one"):e.t("presence_sys.active_sensors_many",{count:D.active_sensors.length})):D?.available_sensors&&D.available_sensors.length&&K.push(D.available_sensors.length===1?e.t("presence_sys.clear_sensors_one"):e.t("presence_sys.clear_sensors_many",{count:D.available_sensors.length})),D?.unavailable_sensors&&D.unavailable_sensors.length&&K.push(D.unavailable_sensors.length===1?e.t("presence_sys.unavailable_sensors_one"):e.t("presence_sys.unavailable_sensors_many",{count:D.unavailable_sensors.length})),z?.has_signature&&z.captured_at?K.push(e.t("presence_sys.calibrated_meta",{when:ci(z.captured_at,e.hass),samples:A(z.sample_count,e.hass,0)})):!oe&&!z?.has_signature&&K.push(e.t("presence_sys.calibrate_hint"));let I=D?.fusion_mode||"weighted",q=Number(D?.fusion_threshold_pct??50),X=D?.fusion_sensors||[],ae=D?.fusion_sensor_choices||[],he=D?.illuminance_sensor_choices||[],ke=String(D?.illuminance_entity||"auto"),ve=String(D?.illuminance_resolved_name||D?.illuminance_resolved_entity||""),x=String(D?.illuminance_lux_display||""),J=D?.illuminance_ambient_pct!==null&&D?.illuminance_ambient_pct!==void 0?Number(D.illuminance_ambient_pct):null,fe=Number(D?.illuminance_dark_lux??.5),Ee=Number(D?.illuminance_bright_lux??40),ze=`fusion-threshold-${C}`,Le=`area-box-${C}`,Ke=e.isHandoffTarget(Le);return l`<div id=${Le} class="area-presence-box${Ke?" handoff-active":""}">
                      <div class="area-box-head">
                        <h4 class="area-box-title">${L}</h4>
                        <div class="area-box-actions">
                          ${z?.has_signature?l`<button
                                type="button"
                                @click=${()=>e.groups.requestClearBleAreaSignature(C,L)}
                                class="btn btn-text btn-compact"
                              >
                                ${e.t("presence_sys.clear_signature")}
                              </button>`:v}
                          ${m.length>0?l`<button
                                type="button"
                                @click=${()=>e.groups.selectBleCalibrateArea(C,!0)}
                                class="btn btn-secondary btn-compact"
                              >
                                ${e.t("presence_sys.calibrate")}
                              </button>`:v}
                        </div>
                      </div>

                      <div class="area-box-badges">
                        ${Z?l`<span class="chip chip-success">${e.t("presence_sys.occupied_chip",{confidence:Q})}</span>`:l`<span class="chip">${e.t("presence_sys.clear_chip")}</span>`}
                        ${ee?l`<span class="chip">${ee}</span>`:v}
                        ${z?.has_signature?l`<span class="chip chip-primary">${z.scanner_count===1?e.t("presence_sys.signature_proxies_one"):e.t("presence_sys.signature_proxies_many",{count:A(z.scanner_count,e.hass,0)})}</span>`:oe?l`<span class="chip">${e.t("sys_overview.ble_proxy")}</span>`:l`<span class="chip chip-warning">${e.t("sys_overview.no_ble_proxy")}</span>`}
                        ${x&&J!==null&&Number.isFinite(J)?l`<span class="chip"
                              >${e.t("presence_sys.lux_chip",{lux:x,level:A(J,e.hass,0)})}</span
                            >`:v}
                      </div>

                      <div class="area-box-meta">${K.join(" \u2022 ")}</div>

                      ${R({label:e.t("presence_sys.presence_mode"),control:l`<select
                          aria-label=${e.t("presence_sys.presence_mode_aria",{area:L})}
                          .value=${S(I)}
                          @change=${Y=>{e.groups.setAreaFusion(C,{mode:Y.currentTarget.value})}}
                        >
                          ${b.map(Y=>l`<option value=${Y.val} .selected=${S(Y.val===I)}>
                                ${Y.label}
                              </option>`)}
                        </select>`})}

                      <details
                        ?open=${e.openFusionAreas.has(C)}
                        @toggle=${Y=>{Y.currentTarget.open?e.openFusionAreas.add(C):e.openFusionAreas.delete(C)}}
                        class="sub-collapsible"
                      >
                        <summary>${e.t("presence_sys.sensor_threshold_drawer")}</summary>
                        <div class="card-content settings-list">
                          ${Zt({id:ze,label:e.t("presence_sys.occupied_at"),ariaLabel:e.t("presence_sys.occupied_at"),description:I==="weighted"?e.t("presence_sys.occupied_at_weighted_desc"):e.t("presence_sys.occupied_at_other_desc"),value:q,min:20,max:95,step:5,unit:"%",disabled:I!=="weighted",hass:e.hass,onCommit:Y=>{e.groups.setAreaFusion(C,{threshold_pct:Y})}})}
                          ${R({label:e.t("presence_sys.sensors_that_count"),description:X.length?e.t("presence_sys.sensors_selected_desc",{selected:X.length,total:ae.length}):e.t("presence_sys.sensors_all_desc"),stacked:!0,control:ae.length?l`<div
                                  role="group"
                                  aria-label=${e.t("presence_sys.sensors_group_aria",{area:L})}
                                  class="pill-list"
                                >
                                  ${ae.map(Y=>{let le=X.includes(Y.entity_id),ne=le?X.filter(He=>He!==Y.entity_id):X.concat([Y.entity_id]);return l`<span class="pill ${le?"enabled":""}">
                                      <button
                                        type="button"
                                        aria-pressed=${String(le)}
                                        title=${Y.entity_id}
                                        @click=${()=>{e.groups.setAreaFusion(C,{sensors:ne})}}
                                        class="pill-toggle"
                                      >
                                        ${le?"\u2713 ":""}${Y.name}
                                      </button>
                                    </span>`})}
                                </div>`:l`<p class="empty-state">
                                  ${e.t("presence_sys.no_area_sensors")}
                                </p>`})}
                          ${he.length>0||ke!=="auto"?l`${R({label:e.t("presence_sys.ambient_sensor"),control:l`<select
                                    aria-label=${e.t("presence_sys.ambient_sensor_aria",{area:L})}
                                    .value=${S(ke)}
                                    @change=${Y=>{e.groups.setAreaIlluminance(C,{entity_id:Y.currentTarget.value})}}
                                  >
                                    <option value="auto" .selected=${S(ke==="auto")}>
                                      ${ve&&ke==="auto"?e.t("presence_sys.ambient_sensor_auto",{sensor:ve}):e.t("presence_sys.ambient_sensor_auto_none")}
                                    </option>
                                    ${he.map(Y=>l`<option
                                          value=${Y.entity_id}
                                          .selected=${S(ke===Y.entity_id)}
                                        >
                                          ${Y.name}${Y.lux_display?` (${Y.lux_display} lx)`:""}
                                        </option>`)}
                                    <option value="disabled" .selected=${S(ke==="disabled")}>
                                      ${e.t("presence_sys.ambient_sensor_disabled")}
                                    </option>
                                  </select>`})}
                                ${ke!=="disabled"?R({label:e.t("presence_sys.calibrate_lux_btn"),description:e.t("presence_sys.ambient_calibration_desc"),stacked:!0,control:l`<div class="lux-bounds-row">
                                        <label class="lux-bound-field">
                                          <span>${e.t("presence_sys.ambient_dark_lux")}</span>
                                          <input
                                            type="number"
                                            class="lux-number-input"
                                            min="0"
                                            max="500"
                                            step="0.1"
                                            aria-label=${`${e.t("presence_sys.ambient_dark_lux")} (${L})`}
                                            .value=${V(String(fe))}
                                            @change=${Y=>{let le=Y.currentTarget,ne=Number(le.value);if(!Number.isFinite(ne)||ne<0){le.value=String(fe);return}if(ne>=Ee){le.value=String(fe),e.showToast(e.t("presence_sys.lux_bounds_error"),!0);return}e.groups.setAreaIlluminance(C,{dark_lux:ne})}}
                                          />
                                        </label>
                                        <label class="lux-bound-field">
                                          <span>${e.t("presence_sys.ambient_bright_lux")}</span>
                                          <input
                                            type="number"
                                            class="lux-number-input"
                                            min="0.5"
                                            max="100000"
                                            step="0.1"
                                            aria-label=${`${e.t("presence_sys.ambient_bright_lux")} (${L})`}
                                            .value=${V(String(Ee))}
                                            @change=${Y=>{let le=Y.currentTarget,ne=Number(le.value);if(!Number.isFinite(ne)||ne<=0){le.value=String(Ee);return}if(ne<=fe){le.value=String(Ee),e.showToast(e.t("presence_sys.lux_bounds_error"),!0);return}e.groups.setAreaIlluminance(C,{bright_lux:ne})}}
                                          />
                                        </label>
                                        <button
                                          type="button"
                                          ?disabled=${e.groups.isCalibratingIlluminance(C)}
                                          class="btn btn-secondary btn-compact"
                                          @click=${()=>{e.groups.calibrateAreaIlluminance(C)}}
                                        >
                                          ${e.groups.isCalibratingIlluminance(C)?e.t("presence_sys.calibrating_lux"):e.t("presence_sys.calibrate_lux_btn")}
                                        </button>
                                      </div>`}):v}`:v}
                        </div>
                      </details>
                    </div>`}):l`<p class="empty-state">
                  ${e.t("presence_sys.empty_areas")}
                </p>`}
          </div>`})}
      </div>

      <div class="column">
        ${U({id:"card-ble-calibration",title:e.t("card.ble_calibration"),subtitle:e.t("presence_sys.calibration_subtitle"),headerActions:m.length>0?l`<button
                  type="button"
                  id="btn-toggle-ble-stream"
                  @click=${()=>e.groups.toggleBleLiveStream(!e.bleLiveStreamActive)}
                  class="btn btn-secondary btn-compact"
                >
                  ${e.bleLiveStreamActive?e.t("presence_sys.pause_stream"):e.t("presence_sys.resume_stream")}
                </button>`:v,footerActions:m.length===0?l`<button
                  type="button"
                  @click=${()=>e.openDiscoveredDevices("card-discovered-ble")}
                  class="btn btn-secondary"
                >
                  ${e.t("presence_sys.open_discovered")}
                </button>`:v,contentClass:"stack",body:m.length===0?l`<p class="empty-state">
                  ${e.t("presence_sys.empty_ble_devices")}
                </p>`:l`<div
                    id="ble-calibrate-target-box"
                    class="calibrate-target-box${e.bleCalibrateHandoffActive?" handoff-active":""}"
                  >
                    ${e.bleCalibrateHandoffActive?l`<div id="ble-calibrate-handoff-banner" class="calibrate-handoff-banner">
                          <span>${e.t("presence_sys.handoff_ready",{area:N,device:g?.title||e.t("presence_sys.your_device")})}</span>
                          <button
                            type="button"
                            @click=${()=>{e.bleCalibrateHandoffActive=!1,e.host.requestUpdate()}}
                            class="btn btn-text btn-compact"
                          >
                            ${e.t("action.dismiss")}
                          </button>
                        </div>`:v}

                    ${R({forId:"ble-survey-device-picker",label:e.t("presence_sys.carried_device"),description:e.t("presence_sys.carried_device_desc"),control:l`<select
                        id="ble-survey-device-picker"
                        .value=${S(g?.subentry_id||"")}
                        @change=${C=>e.groups.selectBleSurveyDevice(C.currentTarget.value)}
                      >
                        ${m.map(C=>l`<option
                              value=${C.subentry_id}
                              .selected=${S(C.subentry_id===g?.subentry_id)}
                            >
                              ${C.title} (${C.active_area_name||e.t("common.unassigned")})
                            </option>`)}
                      </select>`})}

                    ${P?l`<div class="alert">
                          <div class="alert-body">
                            <span>${e.t("presence_sys.live_signal_active")}<strong>${g?.active_area_name||e.t("common.unassigned")}</strong>${e.t("presence_sys.packets_observed",{count:A(h,e.hass,0)})}</span>
                          </div>
                        </div>`:l`<div class="alert alert-warning">
                          <div class="alert-body">
                            <span>${e.t("presence_sys.no_recent_packets_prefix")}<strong>${g?.title||e.t("presence_sys.this_device")}</strong>${e.t("presence_sys.no_recent_packets_suffix")}</span>
                          </div>
                        </div>`}

                    ${R({forId:"ble-calibrate-area-select",label:e.t("presence_sys.standing_in_area"),description:$,stacked:!0,control:l`<div class="input-action-row">
                        <select
                          id="ble-calibrate-area-select"
                          .value=${S(M)}
                          @change=${C=>e.groups.selectBleCalibrateArea(C.currentTarget.value)}
                        >
                          ${w.length?w.map(C=>{let L=y.get(C.area_id),D=L?.has_signature?e.t("presence_sys.suffix_saved"):L&&!L.has_ble_proxy?e.t("presence_sys.suffix_no_proxy"):"";return l`<option
                                  value=${C.area_id}
                                  .selected=${S(C.area_id===M)}
                                >
                                  ${C.area_name}${D}
                                </option>`}):l`<option value="" .selected=${S(!M)}>
                                ${e.t("presence_sys.no_ha_areas_option")}
                              </option>`}
                        </select>
                        <button
                          id="btn-capture-area-signature"
                          type="button"
                          ?disabled=${!g||!M}
                          @click=${()=>{e.groups.captureBleAreaSignature(M)}}
                          class="btn btn-primary"
                        >
                          ${e.t("presence_sys.calibrate_area_btn")}
                        </button>
                      </div>`})}
                  </div>

                  <div class="subsection-title">${e.t("presence_sys.nearby_proxies")}</div>
                  ${_.length?ge(_,(C,L)=>`${C.area_id}::${C.scanner_source||L}`,C=>{let L=C.scanner_source||"",D=C.area_name||e.t("presence_sys.unassigned_proxy"),z=C.scanner_name||L||e.t("sys_overview.ble_proxy"),_e=`--signal-pct:${ui(C.effective_rssi)}%`,Q=Number(C.offset_db||0),ee=`${Q>=0?"+":""}${A(Q,e.hass,1)} dB`,oe=C.raw_rssi!==null&&C.raw_rssi!==void 0?`${A(C.raw_rssi,e.hass,0)} dBm`:e.t("common.unknown"),O=C.effective_rssi!==null&&C.effective_rssi!==void 0?`${A(C.effective_rssi,e.hass,0)} dBm`:e.t("signal.no_reading"),re=C.distance_m!==null&&C.distance_m!==void 0?` \u2022 ~${zt(C.distance_m,e.hass,C.distance_ft)}`:"",K=C.age_seconds!==null&&C.age_seconds!==void 0?` \u2022 ${gs(C.age_seconds,e.hass)}${C.is_fresh===!1?e.t("presence_sys.stale_suffix"):""}`:"",I=Math.abs(Q)>=.1?e.t("presence_sys.trim_suffix",{offset:ee}):"",q=`${O}${re}${K}${I}`;return l`<div class="signal-row ${C.is_winner?"winner":""}">
                            <div class="signal-row-head">
                              <span class="signal-row-title">
                                <span class="row-label">${D}</span>
                                <span class="chip">${z}</span>
                                ${C.area_name?v:l`<span class="chip chip-warning">${e.t("presence_sys.assign_area_in_ha")}</span>`}
                                ${C.is_winner?l`<span class="chip chip-primary">${e.t("presence_sys.active_winner")}</span>`:v}
                              </span>
                              <span class="signal-meta">${q}</span>
                            </div>
                            <div class="signal-track">
                              <div class="signal-fill" style=${_e}></div>
                            </div>
                            ${L?l`<details
                                  ?open=${e.openProxyTrims.has(L)}
                                  @toggle=${X=>{X.currentTarget.open?e.openProxyTrims.add(L):e.openProxyTrims.delete(L)}}
                                  class="sub-collapsible proxy-trim-details"
                                >
                                  <summary>${e.t("presence_sys.antenna_trim")}</summary>
                                  <div class="proxy-trim-body">
                                    <span class="help-text">${e.t("presence_sys.antenna_trim_help",{raw:oe,offset:ee})}</span>
                                    <div class="input-action-row">
                                      <button
                                        type="button"
                                        @click=${()=>{e.groups.setBleScannerOffset(L,Q-1)}}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        ${e.t("presence_sys.minus_one_db")}
                                      </button>
                                      <button
                                        type="button"
                                        @click=${()=>{e.groups.setBleScannerOffset(L,Q+1)}}
                                        class="btn btn-secondary btn-compact"
                                      >
                                        ${e.t("presence_sys.plus_one_db")}
                                      </button>
                                      <button
                                        type="button"
                                        @click=${()=>{e.groups.setBleScannerOffset(L,0)}}
                                        class="btn btn-text btn-compact"
                                      >
                                        ${e.t("action.reset")}
                                      </button>
                                    </div>
                                  </div>
                                </details>`:v}
                          </div>`}):l`<p class="empty-state">
                        ${e.t("presence_sys.empty_survey")}
                      </p>`}`})}

        <details
          id="card-advanced-ble-settings"
          ?open=${e.advancedBleOpen}
          @toggle=${C=>{e.advancedBleOpen=C.currentTarget.open}}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">${e.t("card.advanced_ble")}</h3>
              <p class="card-subtitle">
                ${e.t("presence_sys.advanced_subtitle")}
              </p>
            </div>
          </summary>
          <div class="card-content settings-list">
            ${R({forId:"sys-ble_away_timeout_s",label:e.t("presence_sys.away_timeout"),description:e.t("presence_sys.away_timeout_desc"),control:l`<input
                type="number"
                id="sys-ble_away_timeout_s"
                min="30"
                max="900"
                step="15"
                .value=${V(String(o?.ble_away_timeout_s??180))}
                @change=${C=>{let L=Number(C.currentTarget.value);Number.isFinite(L)&&e.entity.stageSystemSetting("ble_away_timeout_s",Math.round(L),"sys-ble_away_timeout_s")}}
              />`})}
            ${R({forId:"sys-ble_max_radius_m",label:a?e.t("presence_sys.max_radius_ft"):e.t("presence_sys.max_radius"),description:a?e.t("presence_sys.max_radius_ft_desc"):e.t("presence_sys.max_radius_desc"),control:l`<input
                type="number"
                id="sys-ble_max_radius_m"
                min=${a?"6.5":"2"}
                max=${a?"164":"50"}
                step=${a?"1":"0.5"}
                .value=${V(String(s))}
                @change=${C=>{let L=Number(C.currentTarget.value);if(Number.isFinite(L)){let D=a?Math.max(2,Math.min(50,Math.round(L/Gi*100)/100)):L;e.entity.stageSystemSetting("ble_max_radius_m",D,"sys-ble_max_radius_m")}}}
              />`})}
            ${R({forId:"sys-ble_max_velocity_mps",label:a?e.t("presence_sys.max_speed_fps"):e.t("presence_sys.max_speed"),description:a?e.t("presence_sys.max_speed_fps_desc"):e.t("presence_sys.max_speed_desc"),control:l`<input
                type="number"
                id="sys-ble_max_velocity_mps"
                min=${a?"1.5":"0.5"}
                max=${a?"49":"15"}
                step="0.5"
                .value=${V(String(c))}
                @change=${C=>{let L=Number(C.currentTarget.value);if(Number.isFinite(L)){let D=a?Math.max(.5,Math.min(15,Math.round(L/Gi*100)/100)):L;e.entity.stageSystemSetting("ble_max_velocity_mps",D,"sys-ble_max_velocity_mps")}}}
              />`})}
            ${R({forId:"sys-ble_attenuation",label:e.t("presence_sys.attenuation"),description:e.t("presence_sys.attenuation_desc"),control:l`<input
                type="number"
                id="sys-ble_attenuation"
                min="1.5"
                max="4.5"
                step="0.1"
                .value=${V(String(o?.ble_attenuation??2.2))}
                @change=${C=>{let L=Number(C.currentTarget.value);Number.isFinite(L)&&e.entity.stageSystemSetting("ble_attenuation",L,"sys-ble_attenuation")}}
              />`})}
          </div>
        </details>
      </div>
    </div>
  </section>`}function pc(e){let t=e.state,o=t?.system_config,i=t?.catalog||{},a=o?.remotes_list||[],n=o?.volume_overrides||[],s=o?.remote_groups||[],r=i.areas||[],c=i.ma_speakers||[],u=i.volume_targets||i.remotes||[],p=a.filter(Boolean),d=m=>{let g=(i.remotes||[]).find(_=>_.id===m);return g&&g.name.split(" (")[0]||m};return l`<section id="view-remotes">
    <div class="columns">
      <div class="column">
        ${U({title:e.t("card.remote_controls"),subtitle:e.t("remotes.controls_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.entity.addStringListRow("remotes_list","",10)}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("remotes.add_remote")}
          </button>`,body:Io({id:"remotes-list",items:a,choices:i.remotes,emptyOptionLabel:e.t("remotes.choose_remote"),emptyStateText:e.t("remotes.empty_remotes"),selectAriaLabel:e.t("remotes.remote_aria"),removeAriaLabel:e.t("remotes.remove_remote"),slotLabel:m=>m===0?e.t("remotes.slot_primary"):e.t("remotes.slot_n",{index:m+1}),onReorder:(m,g)=>e.entity.reorderStringListRows("remotes_list",m,g),onChange:(m,g)=>e.entity.updateStringListRow("remotes_list",m,g),onRemove:m=>e.entity.removeStringListRow("remotes_list",m)})})}

        ${U({id:"card-volume-overrides",title:e.t("card.volume_overrides"),subtitle:e.t("remotes.overrides_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.entity.addVolumeOverrideRow()}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("remotes.add_override")}
          </button>`,body:l`<div id="volume-overrides-list" class="stack">
            ${n.length?n.map((m,g)=>l`<div class="list-row">
                    <div class="list-row-main">
                      <div class="stacked-field">
                        <span class="field-label">${e.t("remotes.when_playing_on")}</span>
                        <select
                          aria-label=${e.t("remotes.speaker_aria")}
                          .value=${S(m.speaker)}
                          @change=${_=>e.entity.updateVolumeOverrideRow(g,"speaker",_.currentTarget.value)}
                        >
                          ${Ne(c,m.speaker,e.t("remotes.choose_speaker"))}
                        </select>
                      </div>
                      <div class="stacked-field">
                        <span class="field-label">${e.t("remotes.change_volume_on")}</span>
                        <select
                          aria-label=${e.t("remotes.volume_target_aria")}
                          .value=${S(m.target)}
                          @change=${_=>e.entity.updateVolumeOverrideRow(g,"target",_.currentTarget.value)}
                        >
                          ${Ne(u,m.target,e.t("remotes.choose_volume_target"))}
                        </select>
                      </div>
                    </div>
                    ${Se(e.t("remotes.remove_override_aria"),()=>e.entity.removeVolumeOverrideRow(g))}
                  </div>`):l`<p class="empty-state">${e.t("remotes.empty_overrides")}</p>`}
          </div>`})}
      </div>

      <div class="column">
        ${U({id:"card-remote-groups",handoffActive:e.isHandoffTarget("card-remote-groups"),title:e.t("card.remote_groups"),subtitle:e.t("remotes.groups_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.entity.addRemoteGroupRow()}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("remotes.add_group")}
          </button>`,body:l`<div id="remote-groups-list" class="stack">
            ${s.length?s.map((m,g)=>{let _=Array.isArray(m.remotes)?m.remotes:[],h=_.filter(f=>p.includes(f)).concat(p.filter(f=>!_.includes(f))),b=`rg-name-${m.id}`,y=`rg-area-${m.id}`;return l`<div class="list-block">
                    <div class="list-row-head">
                      <div class="list-row-main">
                        <div class="stacked-field">
                          <label for=${b}>${e.t("remotes.group_name")}</label>
                          <input
                            type="text"
                            id=${b}
                            placeholder=${e.t("remotes.group_name_placeholder")}
                            .value=${V(m.name||"")}
                            @change=${f=>e.entity.updateRemoteGroupField(m.id,"name",f.currentTarget.value)}
                          />
                        </div>
                        <div class="stacked-field">
                          <label for=${y}>${e.t("remotes.loads_in_area")}</label>
                          <select
                            id=${y}
                            aria-label=${e.t("remotes.area_aria")}
                            .value=${S(m.area_id||"")}
                            @change=${f=>e.entity.updateRemoteGroupField(m.id,"area_id",f.currentTarget.value)}
                          >
                            <option value="" .selected=${S(!m.area_id)}>
                              ${e.t("remotes.no_area_option")}
                            </option>
                            ${r.map(f=>l`<option value=${f.id} .selected=${S(f.id===m.area_id)}>
                                  ${f.name}
                                </option>`)}
                          </select>
                        </div>
                      </div>
                      ${Se(e.t("remotes.delete_group_aria",{name:m.name||m.id}),()=>e.entity.removeRemoteGroupRow(m.id))}
                    </div>
                    <div class="stacked-field">
                      <span id=${`rg-remotes-${g}`} class="field-label">
                        ${e.t("remotes.group_remotes_label")}
                      </span>
                      <div role="group" aria-labelledby=${`rg-remotes-${g}`} class="pill-list">
                        ${h.length?h.map(f=>{let k=_.indexOf(f),w=k>=0,M=d(f),E=w?k===0?e.t("remotes.primary_badge",{name:M}):e.t("remotes.numbered_badge",{index:k+1,name:M}):e.t("remotes.add_badge",{name:M});return l`<span class="pill ${w?"enabled":""}">
                                <button
                                  type="button"
                                  aria-pressed=${w?"true":"false"}
                                  @click=${()=>e.entity.toggleRemoteInGroup(m.id,f)}
                                  class="pill-toggle"
                                >
                                  ${E}
                                </button>
                              </span>`}):l`<span class="help-text">
                              ${e.t("remotes.add_remotes_first")}
                            </span>`}
                      </div>
                    </div>
                  </div>`}):l`<p class="empty-state">${e.t("remotes.empty_groups")}</p>`}
          </div>`})}
      </div>
    </div>
  </section>`}var Au="M15,13V5A3,3 0 0,0 9,5V13A5,5 0 1,0 15,13M12,4A1,1 0 0,1 13,5V8H11V5A1,1 0 0,1 12,4Z",Eu="M12,17A2,2 0 0,0 14,15C14,13.89 13.1,13 12,13A2,2 0 0,0 10,15A2,2 0 0,0 12,17M18,8A2,2 0 0,1 20,10V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V10C4,8.89 4.9,8 6,8H7V6A5,5 0 0,1 12,1A5,5 0 0,1 17,6V8H18M12,3A3,3 0 0,0 9,6V8H15V6A3,3 0 0,0 12,3Z",Iu="M19,20H17V11H7V20H5V9L12,5L19,9V20M8,12H16V14H8V12M8,15H16V17H8V15M16,18V20H8V18H16Z",Pu="M12,2A10,10 0 0,1 22,12A10,10 0 0,1 12,22A10,10 0 0,1 2,12A10,10 0 0,1 12,2M12,4A8,8 0 0,0 4,12C4,13.38 4.35,14.68 4.97,15.81L18.81,7.82C17.34,5.53 14.84,4 12,4M19.56,9.5L5.72,17.5C7.19,19.62 9.45,21 12,21A8,8 0 0,0 20,13C20,11.75 19.84,10.58 19.56,9.5M12,11A2,2 0 0,1 14,13A2,2 0 0,1 12,15A2,2 0 0,1 10,13A2,2 0 0,1 12,11Z",Mu="M12,8H4A2,2 0 0,0 2,10V14A2,2 0 0,0 4,16H5V20A1,1 0 0,0 6,21H8A1,1 0 0,0 9,20V16H12L17,20V4L12,8M21.5,12C21.5,13.71 20.54,15.26 19,16V8C20.53,8.75 21.5,10.3 21.5,12Z",Du="M20,2H4A2,2 0 0,0 2,4V22L6,18H20A2,2 0 0,0 22,16V4A2,2 0 0,0 20,2M6,9H18V11H6M14,14H6V12H14M18,8H6V6H18";function zi(e,t){let o=String(t||"").trim();if(!(!o||!e))return e.find(i=>i.id===o)}function mc(e){let t=e.state,o=t?.system_config,i=t?.catalog||{},a=o?.camera_entities||[],n=o?.calendar_entities||[],s=(o?.custom_palettes||[]).filter(d=>ue(d.hex)),r=o?.doorbell_noise_reduction||"strong",c=[{value:"strong",label:e.t("shared.filter_strong")},{value:"light",label:e.t("shared.filter_light")},{value:"off",label:e.t("shared.filter_off")}],u=[{key:"weather_entity",label:e.t("shared.weather_label"),choices:i.weathers},{key:"alarm_entity",label:e.t("shared.security_alarm_label"),choices:i.alarms}],p=[{key:"broadcast_speakers",title:e.t("shared.broadcast_speakers"),addLabel:e.t("shared.add_speaker"),emptyPlaceholder:e.t("shared.choose_speaker"),selectAriaLabel:e.t("shared.speaker_aria"),removeAriaLabel:e.t("shared.remove_speaker"),icon:Mu,maxItems:32,items:o?.broadcast_speakers||[],choices:i.ma_speakers},{key:"thermostat_entities",title:e.t("shared.thermostat_zones"),addLabel:e.t("shared.add_zone"),emptyPlaceholder:e.t("shared.choose_thermostat"),selectAriaLabel:e.t("shared.thermostat_aria"),removeAriaLabel:e.t("shared.remove_thermostat"),icon:Au,maxItems:8,items:o?.thermostat_entities||[],choices:i.climates},{key:"lock_entities",title:e.t("shared.door_locks"),addLabel:e.t("shared.add_lock"),emptyPlaceholder:e.t("shared.choose_lock"),selectAriaLabel:e.t("shared.lock_aria"),removeAriaLabel:e.t("shared.remove_lock"),icon:Eu,maxItems:8,items:o?.lock_entities||[],choices:i.locks},{key:"garage_entities",title:e.t("shared.garage_doors"),addLabel:e.t("shared.add_garage"),emptyPlaceholder:e.t("shared.choose_garage"),selectAriaLabel:e.t("shared.garage_aria"),removeAriaLabel:e.t("shared.remove_garage"),icon:Iu,maxItems:6,items:o?.garage_entities||[],choices:i.garages},{key:"vacuum_entities",title:e.t("shared.robot_vacuums"),addLabel:e.t("shared.add_vacuum"),emptyPlaceholder:e.t("shared.choose_vacuum"),selectAriaLabel:e.t("shared.vacuum_aria"),removeAriaLabel:e.t("shared.remove_vacuum"),icon:Pu,maxItems:6,items:o?.vacuum_entities||[],choices:i.vacuums}];return l`<section id="view-shared_entities">
    <div class="columns">
      <div class="column">
        ${U({id:"card-whole-home",handoffActive:e.isHandoffTarget("card-whole-home"),title:e.t("card.home_hub_weather"),subtitle:e.t("shared.home_hub_subtitle"),contentClass:"stack",body:l`<div class="settings-list">
              ${u.map(d=>{let m=String(o?.[d.key]||""),g=`cfg-${d.key}`;return R({label:d.label,forId:g,control:l`<select
                    id=${g}
                    .value=${S(m)}
                    @change=${_=>e.entity.stageSystemSetting(d.key,_.currentTarget.value,g)}
                  >
                    ${Ne(d.choices,m,e.t("common.none_option"))}
                  </select>`})})}
            </div>

            ${p.map(d=>{let m=d.items.filter(g=>!!String(g||"").trim()).length;return l`<div id="hub-domain-${d.key}" class="hub-domain-box">
                <div class="hub-domain-head">
                  <span class="hub-domain-title">
                    ${we(d.icon)}
                    <span>${d.title}</span>
                    ${m>0?l`<span class="chip chip-primary">
                          ${A(m,e.hass,0)}
                        </span>`:l`<span class="hub-domain-empty">
                          ${e.t("common.none_configured")}
                        </span>`}
                  </span>
                  <button
                    type="button"
                    ?disabled=${d.items.length>=d.maxItems}
                    @click=${()=>e.entity.addStringListRow(d.key,"",d.maxItems)}
                    class="btn btn-secondary btn-compact"
                  >
                    ${d.addLabel}
                  </button>
                </div>
                ${d.items.length?Fe({id:`hub-list-${d.key}`,ariaLabel:d.title,items:d.items,overlay:e.localeOverlay,getKey:g=>g?`ent:${g}`:"empty",getLabel:(g,_)=>zi(d.choices,g)?.name||g||`${d.selectAriaLabel} ${_+1}`,onReorder:(g,_)=>e.entity.reorderStringListRows(d.key,g,_),renderContent:(g,_)=>{let h=zi(d.choices,g);return l`<div class="hub-slot-row">
                          <select
                            aria-label=${d.selectAriaLabel}
                            .value=${S(g)}
                            @change=${b=>e.entity.updateStringListRow(d.key,_,b.currentTarget.value)}
                          >
                            ${Ne(d.choices,g,d.emptyPlaceholder)}
                          </select>
                          ${h?.area_name?l`<span class="hub-slot-meta">
                                <span class="chip">${h.area_name}</span>
                              </span>`:v}
                        </div>`},renderActions:(g,_)=>Se(d.removeAriaLabel,()=>e.entity.removeStringListRow(d.key,_))}):v}
              </div>`})}

            ${(()=>{let d=o?.broadcast_phrases||[],m=d.filter(g=>!!String(g||"").trim()).length;return l`<div id="hub-domain-broadcast_phrases" class="hub-domain-box">
                <div class="hub-domain-head">
                  <span class="hub-domain-title">
                    ${we(Du)}
                    <span>${e.t("shared.broadcast_phrases")}</span>
                    ${m>0?l`<span class="chip chip-primary">
                          ${A(m,e.hass,0)}
                        </span>`:l`<span class="hub-domain-empty">
                          ${e.t("common.none_configured")}
                        </span>`}
                  </span>
                  <button
                    type="button"
                    ?disabled=${d.length>=12}
                    @click=${()=>e.entity.addStringListRow("broadcast_phrases","",12)}
                    class="btn btn-secondary btn-compact"
                  >
                    ${e.t("shared.add_phrase")}
                  </button>
                </div>
                ${d.length?Fe({id:"hub-list-broadcast_phrases",ariaLabel:e.t("shared.broadcast_phrases"),items:d,overlay:e.localeOverlay,getKey:(g,_)=>g?`phrase:${g}`:`empty:${_}`,getLabel:(g,_)=>g||`${e.t("shared.phrase_aria")} ${_+1}`,onReorder:(g,_)=>e.entity.reorderStringListRows("broadcast_phrases",g,_),renderContent:(g,_)=>l`<div class="hub-slot-row">
                        <input
                          type="text"
                          maxlength="64"
                          aria-label=${`${e.t("shared.phrase_aria")} ${_+1}`}
                          placeholder=${e.t("shared.phrase_placeholder")}
                          .value=${V(g)}
                          @change=${h=>e.entity.updateStringListRow("broadcast_phrases",_,h.currentTarget.value)}
                        />
                      </div>`,renderActions:(g,_)=>Se(e.t("shared.remove_phrase"),()=>e.entity.removeStringListRow("broadcast_phrases",_))}):v}
              </div>`})()}`})}

        ${U({id:"card-calendars",handoffActive:e.isHandoffTarget("card-calendars"),title:e.t("card.calendars"),subtitle:e.t("shared.calendars_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.entity.addStringListRow("calendar_entities","",50)}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("shared.add_calendar")}
          </button>`,body:Io({id:"calendars-list",items:n,choices:i.calendars,emptyOptionLabel:e.t("shared.choose_calendar"),emptyStateText:e.t("shared.empty_calendars"),selectAriaLabel:e.t("shared.calendar_aria"),removeAriaLabel:e.t("shared.remove_calendar"),onReorder:(d,m)=>e.entity.reorderStringListRows("calendar_entities",d,m),onChange:(d,m)=>e.entity.updateStringListRow("calendar_entities",d,m),onRemove:d=>e.entity.removeStringListRow("calendar_entities",d)})})}
      </div>

      <div class="column">
        ${U({id:"card-cameras-doorbell",handoffActive:e.isHandoffTarget("card-cameras-doorbell"),title:e.t("card.cameras_doorbell"),subtitle:e.t("shared.cameras_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.entity.addStringListRow("camera_entities","",10)}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("shared.add_camera")}
          </button>`,contentClass:"stack",body:l`<div class="settings-list">
              ${se({id:"cfg-doorbell_noise_reduction",label:e.t("shared.doorbell_filter_label"),description:e.t("shared.doorbell_filter_desc"),value:r,rawOptions:c,onChange:d=>e.entity.stageSystemSetting("doorbell_noise_reduction",d,"cfg-doorbell_noise_reduction")})}
            </div>

            ${Io({id:"cameras-list",items:a,choices:i.cameras,emptyOptionLabel:e.t("shared.choose_camera"),emptyStateText:e.t("shared.empty_cameras"),selectAriaLabel:e.t("shared.camera_aria"),removeAriaLabel:e.t("shared.remove_camera"),stacked:!0,slotLabel:d=>d===0?e.t("shared.camera_slot_primary"):e.t("shared.camera_slot_n",{index:d+1}),slotMeta:d=>{let m=sn(e,d),g=m.meta,_=[];m.label&&_.push(l`<span class="chip chip-primary">
                      ${e.t("shared.cam_cap_label",{label:m.label})}
                    </span>`);let h=String(g?.stream_kind||"").trim().toLowerCase();if(h==="rtsp"?_.push(l`<span class="chip">${e.t("shared.cam_cap_rtsp")}</span>`):h==="mjpeg"?_.push(l`<span class="chip">${e.t("shared.cam_cap_mjpeg")}</span>`):h==="snapshot"&&_.push(l`<span class="chip">${e.t("shared.cam_cap_snapshot")}</span>`),g?.is_doorbell&&_.push(l`<span class="chip chip-primary">${e.t("shared.cam_cap_doorbell")}</span>`),m.showListen&&_.push(l`<span class="chip">${e.t("shared.cam_cap_listen")}</span>`),m.showTalk&&_.push(l`<span class="chip">${e.t("shared.cam_cap_talk")}</span>`),m.showReply&&_.push(l`<span class="chip">${e.t("shared.cam_cap_reply")}</span>`),m.unlockEntity){let b=zi(i.locks,m.unlockEntity)||zi(i.garages,m.unlockEntity),y=b?.name?te(b.name):m.unlockEntity;_.push(l`<span class="chip">
                      ${e.t("shared.cam_cap_unlock",{entity:y})}
                    </span>`)}return _.length>0?l`<span class="hub-slot-meta">${_}</span>`:v},extraActions:d=>l`<button
                  type="button"
                  ?disabled=${!d}
                  @click=${()=>ll(e,d)}
                  class="btn btn-text btn-compact"
                >
                  ${e.t("action.configure")}
                </button>
                <button
                  type="button"
                  ?disabled=${!d}
                  @click=${()=>{e.entity.previewCamera(d)}}
                  class="btn btn-text btn-compact"
                >
                  ${e.t("shared.preview")}
                </button>`,onReorder:(d,m)=>e.entity.reorderStringListRows("camera_entities",d,m),onChange:(d,m)=>e.entity.updateStringListRow("camera_entities",d,m),onRemove:d=>e.entity.removeStringListRow("camera_entities",d)})}

            ${e.cameraPreviewUrl?l`<div id="cam-preview-box" class="cam-preview">
                  <div class="input-action-row">
                    <span class="field-label">
                      ${e.t("shared.preview_heading",{entity:e.activeCameraPreviewEntity})}
                    </span>
                    <button
                      type="button"
                      @click=${()=>{e.entity.previewCamera(e.activeCameraPreviewEntity,!0)}}
                      class="btn btn-secondary btn-compact"
                    >
                      ${e.t("action.refresh")}
                    </button>
                    <button
                      type="button"
                      @click=${()=>e.entity.closeCameraPreview()}
                      class="btn btn-text btn-compact"
                    >
                      ${e.t("action.close")}
                    </button>
                  </div>
                  <img
                    id="cam-preview-img"
                    src=${e.cameraPreviewUrl}
                    alt=${e.t("shared.camera_preview_alt")}
                  />
                </div>`:v}`})}

        ${U({id:"card-custom-colors",handoffActive:e.isHandoffTarget("card-custom-colors"),title:e.t("card.custom_colors"),subtitle:e.t("shared.colors_subtitle"),headerActions:l`<button
            type="button"
            @click=${()=>e.tools.openColorWheelModal("system")}
            class="btn btn-secondary btn-compact"
          >
            ${e.t("shared.add_color")}
          </button>`,contentClass:"settings-list",body:l`<div id="sys-custom-palettes-list" class="settings-list">
            ${s.length?s.map(d=>{let m=d.hex.toUpperCase(),g=`--swatch-color:${m}`;return R({labelHtml:l`<span class="row-label">
                      <span class="swatch" style=${g} aria-hidden="true"></span>
                      ${d.name||m}
                    </span>`,description:l`<code>${m}</code>`,control:Se(e.t("shared.delete_color_aria",{name:d.name||m}),()=>e.entity.deleteCustomPalette(m))})}):l`<p class="empty-state">${e.t("shared.empty_colors")}</p>`}
          </div>`})}
      </div>
    </div>
  </section>`}var Ru="https://github.com/slampton/ha-latter",Lu="https://github.com/slampton/ha-latter/issues";function gc(e){let t=e.state,o=t?.system_devices||[],i=o.filter(f=>f.kind!=="ble_tag"),a=o.length-i.length,s=(t?.system_config?.camera_entities||[]).map(f=>String(f||"").trim()).filter(Boolean)[0]||"",r=!!(s&&i.length>0),c=s?i.length?e.t("tools_sys.doorbell_desc_ready",{camera:s}):e.t("tools_sys.doorbell_desc_no_dev"):e.t("tools_sys.doorbell_desc_no_cam"),u=!!t?.has_security_pin,p=e.announceMode==="broadcast",d=t?.system_info,m=d?.ha_version||e.hass?.config?.version||e.t("common.unknown"),g=d?.integration_version||t?.version||"",_=g?`v${g}`:e.t("common.unknown"),h=d?.min_firmware_sdk_rev?String(d.min_firmware_sdk_rev):e.t("common.unknown"),b=`rev ${String(d?.studio_rev??46)}`,y=f=>{let k=f;if(k.key!=="ArrowLeft"&&k.key!=="ArrowRight")return;k.preventDefault();let w=e.announceMode==="notify"?"broadcast":"notify";e.announceMode=w,e.host.requestUpdate(),k.currentTarget.parentElement?.querySelector(`[data-mode="${w}"]`)?.focus()};return l`<section id="view-system_tools">
    <div class="columns">
      <div class="column">
        ${U({id:"card-notifications-announcements",title:e.t("card.notifications_announcements"),subtitle:e.t("tools_sys.announce_subtitle"),contentClass:"stack",body:l`<div
              role="radiogroup"
              aria-label=${e.t("tools_sys.announce_mode_aria")}
              class="segmented"
            >
              <button
                type="button"
                data-mode="notify"
                tabindex=${p?"-1":"0"}
                aria-checked=${String(!p)}
                @click=${()=>{e.announceMode="notify",e.host.requestUpdate()}}
                @keydown=${y}
                role="radio"
              >
                ${e.t("tools_sys.screen_notification")}
              </button>
              <button
                type="button"
                data-mode="broadcast"
                tabindex=${p?"0":"-1"}
                aria-checked=${String(p)}
                @click=${()=>{e.announceMode="broadcast",e.host.requestUpdate()}}
                @keydown=${y}
                role="radio"
              >
                ${e.t("tools_sys.voice_broadcast")}
              </button>
            </div>

            <div class="stacked-field">
              <label for="ann-target">${e.t("tools_sys.target_label")}</label>
              <select
                id="ann-target"
                .value=${S(e.announceTarget)}
                @change=${f=>{e.announceTarget=f.currentTarget.value||"all",e.host.requestUpdate()}}
              >
                <option value="all" .selected=${S(e.announceTarget==="all")}>
                  ${e.t("tools_sys.all_displays")}
                </option>
                <option
                  value="occupied_areas"
                  .selected=${S(e.announceTarget==="occupied_areas")}
                >
                  ${e.t("tools_sys.occupied_areas_only")}
                </option>
                ${i.map(f=>l`<option
                      value=${f.device_slug}
                      .selected=${S(e.announceTarget===f.device_slug)}
                    >
                      ${e.t("tools_sys.device_prefix",{title:f.title})}
                    </option>`)}
              </select>
            </div>

            ${p?v:l`<div class="stacked-field">
                    <label for="ann-title">${e.t("tools_sys.notification_title")}</label>
                    <input
                      type="text"
                      id="ann-title"
                      placeholder=${e.t("tools_sys.notification_title_placeholder")}
                      .value=${V(e.announceTitle)}
                      @input=${f=>{e.announceTitle=f.currentTarget.value}}
                    />
                  </div>
                  <div class="list-row-main">
                    <div class="stacked-field">
                      <label for="ann-priority">${e.t("tools_sys.priority")}</label>
                      <select
                        id="ann-priority"
                        .value=${S(e.announcePriority)}
                        @change=${f=>{e.announcePriority=f.currentTarget.value}}
                      >
                        <option value="normal" .selected=${S(e.announcePriority==="normal")}>
                          ${e.t("tools_sys.priority_normal")}
                        </option>
                        <option value="warning" .selected=${S(e.announcePriority==="warning")}>
                          ${e.t("tools_sys.priority_warning")}
                        </option>
                        <option value="critical" .selected=${S(e.announcePriority==="critical")}>
                          ${e.t("tools_sys.priority_critical")}
                        </option>
                      </select>
                    </div>
                    <label class="inline-switch">
                      <input
                        type="checkbox"
                        role="switch"
                        .checked=${S(e.announceIncludeCamera)}
                        @change=${f=>{e.announceIncludeCamera=f.currentTarget.checked}}
                        class="switch"
                      />
                      <span>${e.t("tools_sys.include_camera")}</span>
                    </label>
                  </div>`}

            <div class="stacked-field">
              <label for="ann-message">${e.t("tools_sys.message")}</label>
              <textarea
                id="ann-message"
                rows="3"
                placeholder=${e.t("tools_sys.message_placeholder")}
                .value=${V(e.announceMessage)}
                @input=${f=>{e.announceMessage=f.currentTarget.value}}
              ></textarea>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                id="btn-send-announcement"
                @click=${()=>{e.tools.sendAnnouncement()}}
                class="btn btn-primary"
              >
                ${e.t("tools_sys.send_now")}
              </button>
            </div>`})}

        ${U({id:"card-doorbell-intercom-audio",title:e.t("card.doorbell_intercom_audio"),subtitle:e.t("tools_sys.doorbell_subtitle"),contentClass:"settings-list",body:l`${R({label:e.t("tools_sys.source_device"),forId:"doorbell-test-device",description:e.t("tools_sys.source_device_desc"),control:l`<select
                id="doorbell-test-device"
                ?disabled=${!r}
                .value=${S(e.doorbellTestSubentryId)}
                @change=${f=>{e.doorbellTestSubentryId=f.currentTarget.value,e.host.requestUpdate()}}
              >
                ${i.length?i.map(f=>l`<option
                          value=${f.subentry_id}
                          .selected=${S(f.subentry_id===e.doorbellTestSubentryId)}
                        >
                          ${f.title}
                        </option>`):l`<option value="" .selected=${S(!e.doorbellTestSubentryId)}>
                      ${e.t("tools_sys.no_latter_devices")}
                    </option>`}
              </select>`})}
            ${R({id:"row-doorbell-test-reply",label:e.t("tools_sys.test_door_reply"),forId:"doorbell-test-reply",description:c,stacked:!0,control:l`<div class="input-action-row">
                <input
                  type="text"
                  id="doorbell-test-reply"
                  maxlength="160"
                  placeholder=${e.t("tools_sys.doorbell_reply_placeholder")}
                  ?disabled=${!r}
                  .value=${V(e.doorbellTestReply)}
                  @input=${f=>{e.doorbellTestReply=f.currentTarget.value}}
                />
                <button
                  type="button"
                  id="btn-play-door-speaker"
                  ?disabled=${!r}
                  @click=${()=>{e.entity.testDoorbellSpeaker()}}
                  class="btn btn-primary btn-compact"
                >
                  ${e.t("tools_sys.play_door_speaker")}
                </button>
                ${s?v:l`<button
                      type="button"
                      @click=${()=>e.openSystemSection("shared_entities","card-cameras-doorbell")}
                      class="btn btn-text btn-compact"
                    >
                      ${e.t("action.open_shared_entities")}
                    </button>`}
              </div>`})}`})}

        <details
          id="card-system-logs"
          ?open=${e.logsOpen}
          @toggle=${f=>e.tools.onToggleLogsDetails(f.currentTarget.open)}
          class="card"
        >
          <summary class="card-header">
            <div class="card-heading">
              <h3 class="card-title">${e.t("card.system_device_logs")}</h3>
            </div>
          </summary>
          <div class="card-content stack">
            <div class="input-action-row">
              <select
                aria-label=${e.t("tools_sys.logs_filter_aria")}
                .value=${S(e.logFilter)}
                @change=${f=>{e.logFilter=f.currentTarget.value||"all",e.host.requestUpdate()}}
              >
                <option value="all" .selected=${S(e.logFilter==="all")}>
                  ${e.t("tools_sys.logs_all")}
                </option>
                <option value="latter" .selected=${S(e.logFilter==="latter")}>
                  ${e.t("tools_sys.logs_studio")}
                </option>
                <option value="errors" .selected=${S(e.logFilter==="errors")}>
                  ${e.t("tools_sys.logs_errors")}
                </option>
                ${o.map(f=>l`<option
                      value=${`device:${f.device_slug}`}
                      .selected=${S(e.logFilter===`device:${f.device_slug}`)}
                    >
                      ${e.t("tools_sys.device_prefix",{title:f.title})}
                    </option>`)}
              </select>
              <button
                type="button"
                @click=${()=>{e.refreshState({includeLogs:!0})}}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("tools_sys.refresh_logs")}
              </button>
              <button
                type="button"
                @click=${()=>{e.tools.copyLogsToClipboard()}}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("tools_sys.copy_logs")}
              </button>
              <button
                type="button"
                id="btn-clear-internal-logs"
                @click=${()=>{e.tools.clearInternalLogs()}}
                class="btn btn-text btn-compact"
              >
                ${e.t("tools_sys.clear_logs")}
              </button>
              <button
                type="button"
                @click=${()=>e.openHaPage("/config/logs")}
                class="btn btn-text btn-compact"
              >
                ${e.t("action.open_ha_logs")}
              </button>
            </div>
            <pre class="log-output">${e.tools.formatVisibleLogs()}</pre>
          </div>
        </details>
      </div>

      <div class="column">
        ${U({id:"card-backup-restore",handoffActive:e.isHandoffTarget("card-backup-restore"),title:e.t("card.backup_restore"),subtitle:e.t("tools_sys.backup_subtitle"),contentClass:"stack",body:l`<div class="stacked-field">
              <label for="bkp-scope-select">${e.t("tools_sys.export_scope")}</label>
              <div class="input-action-row">
                <select
                  id="bkp-scope-select"
                  .value=${S(e.backupExportScope)}
                  @change=${f=>{e.backupExportScope=f.currentTarget.value,e.host.requestUpdate()}}
                >
                  <option value="system" .selected=${S(e.backupExportScope==="system")}>
                    ${e.t("tools_sys.entire_system")}
                  </option>
                  ${o.map(f=>l`<option
                        value=${`device:${f.subentry_id}`}
                        .selected=${S(e.backupExportScope===`device:${f.subentry_id}`)}
                      >
                        ${e.t("tools_sys.device_prefix",{title:f.title})}
                      </option>`)}
                </select>
                <button
                  type="button"
                  id="btn-download-backup"
                  @click=${()=>{e.tools.exportBackup()}}
                  class="btn btn-secondary"
                >
                  ${e.t("action.download_backup")}
                </button>
              </div>
            </div>

            <div class="stacked-field">
              <label for="input-restore-backup">${e.t("tools_sys.restore_from_backup")}</label>
              <input
                type="file"
                id="input-restore-backup"
                accept=".json,application/json"
                @change=${f=>{let k=f.currentTarget;e.selectedBackupFile=k.files&&k.files[0]?k.files[0]:null,e.host.requestUpdate()}}
              />
            </div>

            <div class="stacked-field">
              <label for="bkp-restore-device">${e.t("tools_sys.target_device_restore")}</label>
              <select
                id="bkp-restore-device"
                .value=${S(e.backupRestoreSubentryId)}
                @change=${f=>{e.backupRestoreSubentryId=f.currentTarget.value,e.host.requestUpdate()}}
              >
                <option value="" .selected=${S(!e.backupRestoreSubentryId)}>
                  ${e.t("tools_sys.auto_system_backup")}
                </option>
                ${o.map(f=>l`<option
                      value=${f.subentry_id}
                      .selected=${S(f.subentry_id===e.backupRestoreSubentryId)}
                    >
                      ${f.title}
                    </option>`)}
              </select>
            </div>

            <div class="input-action-row">
              <button
                type="button"
                id="btn-restore-backup"
                ?disabled=${!e.selectedBackupFile}
                @click=${()=>{e.tools.requestRestoreFromUploadedFile()}}
                class="btn btn-primary"
              >
                ${e.t("action.restore_backup")}
              </button>
            </div>`})}

        ${U({id:"card-perimeter-security",handoffActive:e.isHandoffTarget("card-perimeter-security"),title:e.t("card.perimeter_security_signing"),contentClass:"settings-list",body:l`${R({label:e.t("tools_sys.system_pin_label"),description:e.t("tools_sys.system_pin_desc"),stacked:!0,control:l`<div class="input-action-row">
                <span
                  id="sys-security-pin-status"
                  class="chip ${u?"chip-success":""}"
                >
                  ${u?e.t("status.pin_configured"):e.t("status.pin_not_set")}
                </span>
                <input
                  type="password"
                  id="sys-security-pin-input"
                  inputmode="numeric"
                  pattern="[0-9]*"
                  autocomplete="new-password"
                  aria-label=${e.t("tools_sys.system_pin_aria")}
                  placeholder=${u?e.t("tools_sys.pin_replace_placeholder"):e.t("tools_sys.pin_digits_placeholder")}
                  .value=${V(e.systemPinDraft)}
                  @input=${f=>{e.systemPinDraft=f.currentTarget.value,e.host.requestUpdate()}}
                />
                <button
                  type="button"
                  id="btn-save-security-pin"
                  ?disabled=${e.pinBusy||!e.systemPinDraft.trim()}
                  @click=${()=>{e.tools.saveSecurityPin("system")}}
                  class="btn btn-primary btn-compact"
                >
                  ${e.t("tools_sys.save_pin")}
                </button>
                ${u?l`<button
                      type="button"
                      id="btn-clear-security-pin"
                      ?disabled=${e.pinBusy}
                      @click=${()=>e.tools.requestClearSecurityPin("system")}
                      class="btn btn-danger btn-compact"
                    >
                      ${e.t("tools_sys.clear_pin")}
                    </button>`:v}
              </div>`})}
            ${R({label:e.t("tools_sys.signing_key_label"),description:e.t("tools_sys.signing_key_desc"),control:l`<button
                type="button"
                id="btn-rotate-signing-key"
                @click=${()=>e.tools.requestRotateSigningKey()}
                class="btn btn-secondary btn-compact"
              >
                ${e.t("tools_sys.rotate_signing_key")}
              </button>`})}`})}

        ${U({id:"card-support-diagnostics",title:e.t("card.support_diagnostics"),subtitle:e.t("card.support_subtitle"),contentClass:"stack",footerActions:l`<a
              href=${Ru}
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-text"
            >
              ${e.t("support.documentation")}
            </a>
            <a
              href=${Lu}
              target="_blank"
              rel="noopener noreferrer"
              class="btn btn-text"
            >
              ${e.t("support.report_issue")}
            </a>`,body:l`<div class="kv-list">
              <div class="kv-row">
                <span>${e.t("support.ha_version")}</span>
                <strong>${m}</strong>
              </div>
              <div class="kv-row">
                <span>${e.t("support.integration_version")}</span>
                <strong>${_}</strong>
              </div>
              <div class="kv-row">
                <span>${e.t("support.sdk_rev")}</span>
                <strong>${h}</strong>
              </div>
              <div class="kv-row">
                <span>${e.t("support.studio_rev")}</span>
                <strong>${b}</strong>
              </div>
              <div class="kv-row">
                <span>${e.t("support.managed_devices")}</span>
                <strong>${e.t("support.managed_devices_value",{total:o.length,displays:i.length,trackers:a})}</strong>
              </div>
            </div>
            <div class="input-action-row">
              <button
                type="button"
                id="btn-download-system-diagnostics"
                @click=${()=>{e.tools.downloadSystemDiagnostics()}}
                class="btn btn-primary"
              >
                ${e.t("support.download_system_diagnostics")}
              </button>
              <button
                type="button"
                id="btn-copy-system-info"
                @click=${()=>{e.tools.copySystemInfoSummary()}}
                class="btn btn-secondary"
              >
                ${e.t("support.copy_summary")}
              </button>
            </div>`})}
      </div>
    </div>
  </section>`}function _c(e){if(e.currentScope==="system")switch(e.currentViewId){case"shared_entities":return mc(e);case"photos":return dc(e);case"remotes":return pc(e);case"system_sync":return rc(e);case"area_tracking":return uc(e);case"system_tools":return gc(e);default:return cc(e)}let t=e.currentViewId;if(t==="discovered_devices")return Jl(e);if(!e.deviceSelected||t==="select_device_prompt")return ec(e);switch(t){case"display":return e.deviceHasView("display")?Bl(e):wt(e);case"interface":return e.deviceHasView("interface")?Hl(e):wt(e);case"audio_voice":return e.deviceHasView("audio_voice")?Rl(e):wt(e);case"power":return e.deviceHasView("power")?Wl(e):wt(e);case"presence":return e.deviceHasView("presence")?jl(e):wt(e);case"tools":return e.deviceHasView("tools")?Xl(e):wt(e);default:return wt(e)}}var Ou=[{viewId:"system_overview",labelKey:"view.system_overview"},{viewId:"shared_entities",labelKey:"view.shared_entities"},{viewId:"photos",labelKey:"view.photos"},{viewId:"remotes",labelKey:"view.remotes"},{viewId:"system_sync",labelKey:"view.system_sync"},{viewId:"area_tracking",labelKey:"view.area_tracking"},{viewId:"system_tools",labelKey:"view.system_tools"}],Bu=[{viewId:"dashboard",labelKey:"view.dashboard"},{viewId:"display",labelKey:"view.display",id:"nav-btn-display"},{viewId:"interface",labelKey:"view.interface",id:"nav-btn-interface"},{viewId:"audio_voice",labelKey:"view.audio_voice",id:"nav-btn-audio_voice"},{viewId:"power",labelKey:"view.power",id:"nav-btn-power"},{viewId:"presence",labelKey:"view.presence"},{viewId:"tools",labelKey:"view.tools"}],vn=class extends ot{static styles=Dl;store;_narrow=!1;_route=null;_panel=null;_routeInitialized=!1;_lastRouteHeadingKey="";constructor(){super(),this.store=new Li(this),this.addController(this.store)}connectedCallback(){this._routeInitialized||(this._routeInitialized=!0,this._applyRoute()),super.connectedCallback()}_syncShowMenu(t){let o=this._narrow||t?.dockedSidebar==="always_hidden";this.toggleAttribute("show-menu",o)}set hass(t){this.toggleAttribute("dark",!!t?.themes?.darkMode),this._syncShowMenu(t),this.store.setHass(t)}get hass(){return this.store.hass}set narrow(t){let o=!!t;this._narrow!==o&&(this._narrow=o,this.toggleAttribute("narrow",o),this._syncShowMenu(this.store.hass))}get narrow(){return this._narrow}set panel(t){this._panel=t}get panel(){return this._panel}set route(t){let o=this._route?.path??null;this._route=t,this._routeInitialized&&t&&t.path!==o&&this._applyRoute()}get route(){return this._route}_applyRoute(){this.store.applyRoute(this._route)}_onNavLinkClick(t,o){t.defaultPrevented||t.button!==0||t.metaKey||t.ctrlKey||t.shiftKey||t.altKey||(t.preventDefault(),o())}_onRootKeyDown(t){if(t.ctrlKey||t.metaKey||t.altKey||t.key==="Escape"||t.key==="Tab")return;let i=(typeof t.composedPath=="function"?t.composedPath():[])[0]??t.target;if(!i||typeof i.tagName!="string")return;let a=i.tagName.toUpperCase();(a==="INPUT"||a==="TEXTAREA"||a==="SELECT")&&t.stopPropagation()}_onMainFocusOut(t){let i=(typeof t.composedPath=="function"?t.composedPath():[])[0]??t.target;if(!i||typeof i.tagName!="string"||i.getAttribute("role")==="combobox")return;let a=i.tagName.toUpperCase();if(a==="TEXTAREA"){this.store.entity.flushAllPendingSettings();return}if(a==="INPUT"){let n=String(i.type||"text").toLowerCase();(n==="text"||n==="number"||n==="search"||n==="password"||n==="tel"||n==="url"||n==="email")&&this.store.entity.flushAllPendingSettings()}}_onScopeTabKeyDown(t){if(t.key!=="ArrowLeft"&&t.key!=="ArrowRight"&&t.key!=="Home"&&t.key!=="End")return;t.preventDefault();let o=this.store.currentScope==="device",i;t.key==="Home"?i="device":t.key==="End"?i="system":i=o?"system":"device",i==="device"?(this.store.openDevicesLanding(),this.renderRoot.querySelector("#tab-scope-device")?.focus()):(this.store.setScope("system"),this.renderRoot.querySelector("#tab-scope-system")?.focus())}updated(t){let o=this.renderRoot;Tl(o,this.store);let i=o.getElementById("latter-confirm-modal");ws(i,this.store.confirmModal.open);let a=`${this.store.currentScope}|${this.store.currentViewId}|${this.store.activeSubentryId}`;if(this._lastRouteHeadingKey&&this._lastRouteHeadingKey!==a){let n=this.store.pageSubtitle?`${this.store.pageTitle} \u2014 ${this.store.pageSubtitle}`:this.store.pageTitle;this.store.announcePolite(n);let s=o.activeElement;s&&s.classList?.contains("nav-btn")&&o.getElementById("unified-page-title")?.focus?.({preventScroll:!0})}this._lastRouteHeadingKey=a}_renderDeviceNav(){let t=this.store.activeSubentryId,o=encodeURIComponent(t),i=this.store.pageSubtitle||this.store.t("common.unknown"),a=Bu.filter(n=>this.store.deviceHasView(n.viewId));return l`<nav
      id="nav-scope-device"
      aria-label=${this.store.t("nav.device_pages_label")}
      class="nav-list"
    >
      <a
        href="/latter/devices"
        @click=${n=>this._onNavLinkClick(n,()=>this.store.openDevicesLanding())}
        class="nav-btn nav-back-btn"
      >
        <span>${this.store.t("nav.back_managed")}</span>
      </a>
      <div id="nav-selected-device-label" class="nav-device-title">
        ${i}
      </div>
      ${a.map(n=>{let s=this.store.currentViewId===n.viewId,r=qt[n.viewId];return l`<a
          href="/latter/devices/${o}/${r}"
          id=${n.id||v}
          data-view=${n.viewId}
          aria-current=${s?"page":v}
          @click=${c=>this._onNavLinkClick(c,()=>this.store.switchView(n.viewId))}
          class="nav-btn ${s?"active":""}"
        >
          <span>${this.store.t(n.labelKey)}</span>
        </a>`})}
    </nav>`}_renderSidebar(){let t=this.store.currentScope==="device",o=(this.store.state?.system_devices||[]).length,i=(this.store.state?.discovered_latter_devices||[]).length,a=!this.store.deviceSelected||this.store.currentViewId==="select_device_prompt"||this.store.currentViewId==="discovered_devices",n=t&&a&&this.store.currentViewId!=="discovered_devices",s=t&&this.store.currentViewId==="discovered_devices";return l`<aside class="sidebar">
      <div role="tablist" aria-label=${this.store.t("nav.scope_label")} class="scope-tabs">
        <button
          type="button"
          id="tab-scope-device"
          role="tab"
          aria-selected=${t?"true":"false"}
          tabindex=${t?"0":"-1"}
          @click=${()=>this.store.openDevicesLanding()}
          @keydown=${r=>this._onScopeTabKeyDown(r)}
          class="scope-tab ${t?"active":""}"
        >
          ${this.store.t("nav.devices")}
        </button>
        <button
          type="button"
          id="tab-scope-system"
          role="tab"
          aria-selected=${t?"false":"true"}
          tabindex=${t?"-1":"0"}
          @click=${()=>this.store.setScope("system")}
          @keydown=${r=>this._onScopeTabKeyDown(r)}
          class="scope-tab ${t?"":"active"}"
        >
          ${this.store.t("nav.system")}
        </button>
      </div>

      ${t?a?l`<nav
              id="nav-scope-devices-list"
              aria-label=${this.store.t("nav.devices_list_label")}
              class="nav-list"
            >
              <a
                href="/latter/devices"
                data-view="select_device_prompt"
                aria-current=${n?"page":v}
                @click=${r=>this._onNavLinkClick(r,()=>this.store.openDevicesLanding())}
                class="nav-btn ${n?"active":""}"
              >
                <span>${this.store.t("nav.managed")}</span>
                <span id="nav-system-count" class="nav-badge">
                  ${this.store.state?String(o):this.store.t("common.unknown")}
                </span>
              </a>
              <a
                href="/latter/devices/discovered"
                data-view="discovered_devices"
                aria-current=${s?"page":v}
                @click=${r=>this._onNavLinkClick(r,()=>this.store.openDiscoveredDevices())}
                class="nav-btn ${s?"active":""}"
              >
                <span>${this.store.t("nav.discovered")}</span>
                ${i>0?l`<span id="nav-discovered-count" class="nav-badge">
                      ${String(i)}
                    </span>`:v}
              </a>
            </nav>`:this._renderDeviceNav():l`<nav
            id="nav-scope-system"
            aria-label=${this.store.t("nav.system_pages_label")}
            class="nav-list"
          >
            ${Ou.map(r=>{let c=this.store.currentViewId===r.viewId,u=Gt[r.viewId];return l`<a
                href="/latter/system/${u}"
                data-view=${r.viewId}
                aria-current=${c?"page":v}
                @click=${p=>this._onNavLinkClick(p,()=>this.store.switchView(r.viewId))}
                class="nav-btn ${c?"active":""}"
              >
                <span>${this.store.t(r.labelKey)}</span>
              </a>`})}
          </nav>`}
    </aside>`}render(){let t=this.store.state,o=this.store.loading&&!t&&!this.store.loadError&&!this.store.studioRevMismatch,i=!o&&this.store.currentScope==="device"&&this.store.deviceSelected&&this.store.deviceLoading,a=this.store.currentScope==="device"&&this.store.deviceSelected&&!this.store.deviceLoading&&this.store.currentViewId!=="select_device_prompt"&&this.store.currentViewId!=="discovered_devices"&&!!(t?.live?.fw_update_available&&t?.live?.fw_update_entity),n=this.store.pageSubtitle,s=this.store.confirmModal;return l`<div
      id="studio-root"
      @keydown=${r=>this._onRootKeyDown(r)}
      class="studio-root ${o?"is-loading":""}"
    >
      <div
        id="studio-live-polite"
        role="status"
        aria-live="polite"
        aria-atomic="true"
        class="sr-only"
      >
        ${this.store.politeAnnouncement}
      </div>
      <div
        id="studio-live-assertive"
        role="alert"
        aria-live="assertive"
        aria-atomic="true"
        class="sr-only"
      >
        ${this.store.assertiveAnnouncement}
      </div>

      ${this.store.studioRevMismatch?l`<div role="status" class="studio-rev-banner">
            <span>${this.store.t("shell.rev_updated_banner")}</span>
            <button
              type="button"
              @click=${()=>this.store.reloadPage()}
              class="btn btn-primary btn-compact"
            >
              ${this.store.t("shell.reload_page")}
            </button>
          </div>`:v}

      <header class="latter-top-titlebar">
        <div class="titlebar-brand">
          <button
            type="button"
            aria-label=${this.store.t("shell.toggle_ha_sidebar")}
            @click=${()=>this.store.toggleParentHaSidebar()}
            class="btn-icon ha-menu-btn"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 6h18v2H3V6m0 5h18v2H3v-2m0 5h18v2H3v-2Z" />
            </svg>
          </button>
          <span class="titlebar-title">${this.store.t("shell.title")}</span>
        </div>
        <div class="titlebar-actions">
          ${a?l`<button
                type="button"
                id="hdr-update-pill"
                @click=${()=>{this.store.entity.triggerHeaderFirmwareUpdate()}}
                class="btn btn-secondary btn-compact"
              >
                ${this.store.t("shell.install_update")}
              </button>`:v}
        </div>
      </header>

      <div class="app-shell">
        ${this._renderSidebar()}

        <main
          class="main-area"
          @focusin=${r=>this.store.onMainFocusIn(r)}
          @focusout=${r=>this._onMainFocusOut(r)}
        >
          <div class="content-wrap">
            <h1 id="unified-page-title" tabindex="-1" class="page-title">
              <span>${this.store.pageTitle}</span>
              ${n?l`<span class="page-subtitle">${n}</span>`:v}
            </h1>

            ${o?l`<div id="studio-loading" role="status" class="loading-state">
                  ${this.store.t("shell.loading")}
                </div>`:v}

            ${!t&&this.store.loadError?l`<div id="studio-load-error" role="alert" class="alert alert-error">
                  <span id="studio-load-error-text">${this.store.loadError}</span>
                  <button
                    type="button"
                    @click=${()=>{this.store.refreshState()}}
                    class="btn btn-secondary btn-compact"
                  >
                    ${this.store.t("shell.retry")}
                  </button>
                </div>`:v}

            ${i?l`<div id="studio-device-loading" role="status" class="loading-state">
                  ${this.store.t("shell.loading_device")}
                </div>`:t?_c(this.store):v}
          </div>
        </main>
      </div>

      ${xl(this.store)}
      ${Ss({id:"latter-confirm-modal",open:s.open,title:s.title,consequence:s.consequence,blastRadiusCount:s.blastRadiusCount,blastRadiusLabel:s.blastRadiusLabel||void 0,confirmLabel:s.confirmLabel||this.store.t("action.confirm"),cancelLabel:s.cancelLabel||this.store.t("action.cancel"),danger:s.danger,busy:s.busy,confirmButtonId:"btn-confirm-modal-accept",onConfirm:()=>{this.store.runConfirmedAction()},onCancel:()=>this.store.closeConfirm(),onDownloadBackupFirst:s.onDownloadBackupFirst?()=>{s.onDownloadBackupFirst?.()}:null,overlay:this.store.localeOverlay})}

      ${this.store.toastMessage?l`<div class="toast ${this.store.toastIsError?"error":""}">
            <span>${this.store.toastMessage}</span>
            ${this.store.toastIsError?l`<button
                  type="button"
                  aria-label=${this.store.t("shell.dismiss_toast")}
                  @click=${()=>this.store.dismissToast()}
                  class="btn btn-text btn-compact"
                >
                  ${this.store.t("action.dismiss")}
                </button>`:v}
          </div>`:v}
    </div>`}};customElements.get("latter-studio")||customElements.define("latter-studio",vn);export{vn as LatterStudio};
/*! Bundled license information:

@lit/reactive-element/css-tag.js:
  (**
   * @license
   * Copyright 2019 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

@lit/reactive-element/reactive-element.js:
lit-html/lit-html.js:
lit-element/lit-element.js:
lit-html/directive.js:
lit-html/directives/repeat.js:
  (**
   * @license
   * Copyright 2017 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/is-server.js:
  (**
   * @license
   * Copyright 2022 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)

lit-html/directive-helpers.js:
lit-html/directives/live.js:
  (**
   * @license
   * Copyright 2020 Google LLC
   * SPDX-License-Identifier: BSD-3-Clause
   *)
*/
