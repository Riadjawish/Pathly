"use client";
import { Dispatch, SetStateAction, useCallback, useEffect, useState } from "react";
import { ApiSubject, pathlyApi, session } from "../_lib/api";
export type Subject={id:string;name:string;short:string;description:string;topics:number;progress:number;icon:string;tone:string};
const fromApi=(s:ApiSubject):Subject=>({id:s.id,name:s.name,short:s.short_name,description:s.description,topics:s.topics_count,progress:s.progress,icon:s.icon,tone:s.tone});
export function createSubjectId(name:string){return `new-${name.toLowerCase().replace(/[^a-z0-9]+/g,"-")}-${Date.now().toString(36)}`;}
export function useSubjects():[Subject[],Dispatch<SetStateAction<Subject[]>>,boolean]{
 const [subjects,setLocal]=useState<Subject[]>([]);const [loading,setLoading]=useState(true);
 const reload=useCallback(async()=>{if(!session.getAccessToken()){setLoading(false);return;}try{setLocal((await pathlyApi.subjects.list()).map(fromApi));}finally{setLoading(false);}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void reload(),0);return()=>window.clearTimeout(timer);},[reload]);
 const setSubjects=useCallback<Dispatch<SetStateAction<Subject[]>>>((update)=>setLocal(current=>{const next=typeof update==="function"?update(current):update;const oldMap=new Map(current.map(s=>[s.id,s]));const nextIds=new Set(next.map(s=>s.id));for(const old of current)if(!nextIds.has(old.id)&&!old.id.startsWith("new-"))void pathlyApi.subjects.remove(old.id);for(const item of next){if(item.id.startsWith("new-")){void pathlyApi.subjects.create({name:item.name,short_name:item.short,description:item.description,icon:item.icon,tone:item.tone}).then(saved=>setLocal(items=>items.map(value=>value.id===item.id?fromApi(saved):value)));}else{const old=oldMap.get(item.id);if(old&&JSON.stringify(old)!==JSON.stringify(item))void pathlyApi.subjects.update(item.id,{name:item.name,short_name:item.short,description:item.description,icon:item.icon,tone:item.tone});}}return next;}),[]);
 return [subjects,setSubjects,loading];
}
