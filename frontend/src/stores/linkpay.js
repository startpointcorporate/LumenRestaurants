// SPDX-License-Identifier: AGPL-3.0-only
import { defineStore } from 'pinia'
import { call } from '../api'
import { useSessionStore } from './session'
const RPC='konektag_360.link_pay.pos.'
const active=['Prepared','Claimed','Paid','Review']
function storageKey(){const s=useSessionStore();return `lumen:linkpay:${s.posProfile}:${s.user||''}`}
function records(){try{const r=JSON.parse(localStorage.getItem(storageKey())||'null');if(r&&r.orders){r.pending ||= {};if(r.pending.requestKey)r.pending={[r.pending.requestKey]:r.pending};return r}return {orders:{},pending:{}}}catch{return {orders:{},pending:{}}}}
function write(value){try{localStorage.setItem(storageKey(),JSON.stringify(value))}catch{/* page memory still preserves the key */}}
export const useLinkPayStore=defineStore('linkpay',{
 state:()=>({available:false,cashModes:[],attempt:null,version:null,requestKey:null,orderName:null,busy:false,checking:false,uncertain:false,error:false,declined:false,generation:0,basketSignature:null}),
 getters:{locked:s=>s.busy||s.checking||s.uncertain||Boolean(s.attempt&&active.includes(s.attempt.state))},
 actions:{
  remember(){const r=records();const row={requestKey:this.requestKey,order:this.attempt?.order||this.orderName};if(row.order){r.orders[row.order]=row;delete r.pending[this.requestKey]}else r.pending[this.requestKey]=row;write(r)},
  adopt(value){
   if(!value||!['Prepared','Claimed','Paid','Completed','Cancelled','Review'].includes(value.state))throw new Error('Invalid Link Pay state')
   this.attempt=value;this.orderName=value.order;this.uncertain=false;this.error=false;this.declined=false
   if(['Completed','Cancelled'].includes(value.state)){const r=records();delete r.orders[value.order];delete r.pending[this.requestKey];write(r);this.requestKey=null}else this.remember()
   return value
  },
  async context(orderName=null, pendingKey=null){
   const s=useSessionStore();if(!s.posProfile)return null
   const r=records(),row=(orderName?r.orders[orderName]:(pendingKey?r.pending[pendingKey]:null))||((pendingKey&&pendingKey===this.requestKey)||(orderName&&orderName===this.orderName)?{requestKey:this.requestKey}:null)
   // Switching orders never borrows another order's creation key or active intent.
   const previous=this.orderName===orderName?this.attempt:null
   const gen=++this.generation;this.declined=false;this.orderName=orderName;if(this.requestKey!==row?.requestKey)this.basketSignature=null;this.requestKey=row?.requestKey||null;this.attempt=previous;this.uncertain=Boolean(this.requestKey)||Boolean(previous&&active.includes(previous.state));this.checking=true;this.busy=false
   try{const result=await call(RPC+'context',{pos_profile:s.posProfile,order_name:orderName||undefined,request_key:this.requestKey||undefined});if(gen!==this.generation)return null
    this.available=result.available===true;this.cashModes=result.cashModes||[];this.version=result.version||null
    if(result.attempt)return this.adopt(result.attempt)
    this.attempt=null;this.uncertain=Boolean(this.requestKey);this.error=false;return null
   }catch{if(gen===this.generation){this.available=false;this.error=true}throw new Error('Link Pay unavailable')}
   finally{if(gen===this.generation)this.checking=false}
  },
  async prepare(payload,orderName){
   if(this.busy)return null
   const gen=this.generation,hadUncertain=this.uncertain||Boolean(this.attempt&&active.includes(this.attempt.state));this.declined=false;this.basketSignature=JSON.stringify(payload.cart);this.requestKey ||= crypto.randomUUID();this.orderName=orderName||null;this.remember();this.busy=true;this.uncertain=true
   try{const result=await call(RPC+'prepare',{pos_profile:useSessionStore().posProfile,request_key:this.requestKey,payload,order_name:orderName||undefined,expected_version:this.version||undefined});return gen===this.generation?this.adopt(result):null}
   catch(error){if(gen===this.generation){
    if(error.linkPayNoIntent===true&&!hadUncertain){const r=records();if(this.orderName&&r.orders[this.orderName]?.requestKey===this.requestKey)delete r.orders[this.orderName];delete r.pending[this.requestKey];write(r);this.requestKey=null;this.uncertain=false;this.declined=true;this.error=false}
    else this.error=true
   }throw new Error('Link Pay preparation refused')}
   finally{if(gen===this.generation)this.busy=false}
  },
  async refresh(orderName=null){
   const order=this.attempt?.order||orderName||this.orderName;if(!order)return this.context(null,this.requestKey)
   const gen=this.generation;this.busy=true
   try{const result=await call(RPC+'status',{pos_profile:useSessionStore().posProfile,order_name:order});return gen===this.generation?this.adopt(result):null}
   catch{if(gen===this.generation)this.error=true;throw new Error('Link Pay unavailable')}
   finally{if(gen===this.generation)this.busy=false}
  },
  async mutate(action){
   if(this.busy||!this.attempt?.order)return null
   const gen=this.generation;this.busy=true
   try{const result=await call(RPC+action,{pos_profile:useSessionStore().posProfile,order_name:this.attempt.order});return gen===this.generation?this.adopt(result):null}
   catch{if(gen===this.generation)this.error=true;throw new Error('Link Pay unavailable')}
   finally{if(gen===this.generation)this.busy=false}
  },
  savedOrders(){return Object.keys(records().orders)},
  pendingKeys(){return Object.keys(records().pending)},
 },
})
