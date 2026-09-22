import fs from 'node:fs';
import path from 'node:path';

const root = path.dirname(new URL(import.meta.url).pathname.replace(/^\/(?=[A-Za-z]:)/, ''));
const out = decodeURIComponent(root);
const base = 'https://example.org/pc-builder';
const classes = ['Component','CPU','Motherboard','PowerSupply','Socket','PCConfiguration'];
const cpus = [
  ['CPU_AM4_65W', 'Socket_AM4', 65, '120.00'],
  ['CPU_AM4_105W', 'Socket_AM4', 105, '220.00'],
  ['CPU_AM5_65W', 'Socket_AM5', 65, '250.00'],
  ['CPU_LGA1700_125W', 'Socket_LGA1700', 125, '300.00']
];
const boards = [
  ['Motherboard_AM4_A', 'Socket_AM4', '90.00'],
  ['Motherboard_AM4_B', 'Socket_AM4', '140.00'],
  ['Motherboard_AM5', 'Socket_AM5', '180.00'],
  ['Motherboard_LGA1700', 'Socket_LGA1700', '160.00']
];
const psus = [['PSU_450W',450,'50.00'],['PSU_650W',650,'80.00'],['PSU_750W',750,'100.00']];
const sockets = ['Socket_AM4','Socket_AM5','Socket_LGA1700'];
const configs = [
  ['PC_Office_AM4', cpus[0][0], boards[0][0], psus[0][0]],
  ['PC_Performance_AM4', cpus[1][0], boards[1][0], psus[1][0]],
  ['PC_Modern_AM5', cpus[2][0], boards[2][0], psus[1][0]],
  ['PC_Intel_LGA1700', cpus[3][0], boards[3][0], psus[2][0]]
];
const exactObject = (p,c) => `<rdfs:subClassOf><owl:Restriction><owl:onProperty rdf:resource="#${p}"/><owl:qualifiedCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:qualifiedCardinality><owl:onClass rdf:resource="#${c}"/></owl:Restriction></rdfs:subClassOf>`;
const exactData = (p,t) => `<rdfs:subClassOf><owl:Restriction><owl:onProperty rdf:resource="#${p}"/><owl:qualifiedCardinality rdf:datatype="http://www.w3.org/2001/XMLSchema#nonNegativeInteger">1</owl:qualifiedCardinality><owl:onDataRange rdf:resource="http://www.w3.org/2001/XMLSchema#${t}"/></owl:Restriction></rdfs:subClassOf>`;
let xml = `<?xml version="1.0" encoding="UTF-8"?>
<rdf:RDF xmlns="${base}#" xml:base="${base}"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
 xmlns:owl="http://www.w3.org/2002/07/owl#"
 xmlns:xsd="http://www.w3.org/2001/XMLSchema#">
  <owl:Ontology rdf:about="${base}">
    <owl:versionIRI rdf:resource="${base}/1.0"/>
  </owl:Ontology>
`;
for (const name of classes) {
  xml += `\n  <owl:Class rdf:about="#${name}">\n`;
  if (['CPU','Motherboard','PowerSupply'].includes(name)) xml += '    <rdfs:subClassOf rdf:resource="#Component"/>\n';
  if (name==='Component') xml += `    ${exactData('hasPrice','decimal')}\n`;
  if (name==='CPU'||name==='Motherboard') xml += `    ${exactObject('hasSocket','Socket')}\n`;
  if (name==='CPU') xml += `    ${exactData('hasTDP','integer')}\n`;
  if (name==='PowerSupply') xml += `    ${exactData('hasWattage','integer')}\n`;
  if (name==='PCConfiguration') for(const [p,c] of [['hasCPU','CPU'],['hasMotherboard','Motherboard'],['hasPowerSupply','PowerSupply']]) xml += `    ${exactObject(p,c)}\n`;
  xml += '  </owl:Class>\n';
}
for(const group of [['Component','Socket','PCConfiguration'],['CPU','Motherboard','PowerSupply']]) xml += `\n  <owl:AllDisjointClasses><owl:members rdf:parseType="Collection">${group.map(c=>`<rdf:Description rdf:about="#${c}"/>`).join('')}</owl:members></owl:AllDisjointClasses>\n`;
const ops = [['hasSocket',null,'Socket'],['hasCPU','PCConfiguration','CPU'],['hasMotherboard','PCConfiguration','Motherboard'],['hasPowerSupply','PCConfiguration','PowerSupply']];
for (const [p,d,r] of ops) {
  xml += `\n  <owl:ObjectProperty rdf:about="#${p}">\n    <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#FunctionalProperty"/>\n`;
  xml += d ? `    <rdfs:domain rdf:resource="#${d}"/>\n` : '    <rdfs:domain><owl:Class><owl:unionOf rdf:parseType="Collection"><rdf:Description rdf:about="#CPU"/><rdf:Description rdf:about="#Motherboard"/></owl:unionOf></owl:Class></rdfs:domain>\n';
  xml += `    <rdfs:range rdf:resource="#${r}"/>\n`;
  xml += '  </owl:ObjectProperty>\n';
}
for(const [p,d,t] of [['hasTDP','CPU','integer'],['hasWattage','PowerSupply','integer'],['hasPrice','Component','decimal']]) xml += `
  <owl:DatatypeProperty rdf:about="#${p}">
    <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#FunctionalProperty"/>
    <rdfs:domain rdf:resource="#${d}"/>
    <rdfs:range rdf:resource="http://www.w3.org/2001/XMLSchema#${t}"/>
  </owl:DatatypeProperty>
`;
function individual(name,c,objects=[],data=[]) {
  xml += `\n  <owl:NamedIndividual rdf:about="#${name}">\n    <rdf:type rdf:resource="#${c}"/>\n`;
  for(const [p,value] of objects) xml += `    <${p} rdf:resource="#${value}"/>\n`;
  for(const [p,value,type] of data) xml += `    <${p} rdf:datatype="http://www.w3.org/2001/XMLSchema#${type}">${value}</${p}>\n`;
  xml += '  </owl:NamedIndividual>\n';
}
for(const s of sockets) individual(s,'Socket');
for(const [n,s,t,p] of cpus) individual(n,'CPU',[['hasSocket',s]],[['hasTDP',t,'integer'],['hasPrice',p,'decimal']]);
for(const [n,s,p] of boards) individual(n,'Motherboard',[['hasSocket',s]],[['hasPrice',p,'decimal']]);
for(const [n,w,p] of psus) individual(n,'PowerSupply',[],[['hasWattage',w,'integer'],['hasPrice',p,'decimal']]);
for(const [n,c,m,p] of configs) individual(n,'PCConfiguration',[['hasCPU',c],['hasMotherboard',m],['hasPowerSupply',p]]);
const names = [...sockets,...cpus.map(x=>x[0]),...boards.map(x=>x[0]),...psus.map(x=>x[0]),...configs.map(x=>x[0])];
xml += `\n  <owl:AllDifferent><owl:distinctMembers rdf:parseType="Collection">\n${names.map(n=>`    <rdf:Description rdf:about="#${n}"/>`).join('\n')}\n  </owl:distinctMembers></owl:AllDifferent>\n</rdf:RDF>\n`;
fs.writeFileSync(path.join(out,'PC_Builder.owl'),xml,'utf8');
console.log(`Saved PC_Builder.owl: 6 classes, 4 object properties, 3 data properties, ${names.length} individuals.`);
