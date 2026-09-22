import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const xsd = 'http://www.w3.org/2001/XMLSchema#';
// Extend the preserved practice-2 facts; regeneration never reads its own output.
let xml = fs.readFileSync(path.join(root, 'validation/practice2/PC_Builder.owl'), 'utf8');
xml = xml.replace('https://example.org/pc-builder/1.0', 'https://example.org/pc-builder/2.0');
const ref = n => `<rdf:Description rdf:about="#${n}"/>`;
const group = (kind, members) => `<owl:Class><owl:${kind} rdf:parseType="Collection">${members.join('')}</owl:${kind}></owl:Class>`;
const union = (...members) => group('unionOf', members);
const and = (...members) => group('intersectionOf', members);
const restriction = (p, content) => `<owl:Restriction><owl:onProperty rdf:resource="#${p}"/>${content}</owl:Restriction>`;
const some = (p, c) => restriction(p, `<owl:someValuesFrom rdf:resource="#${c}"/>`);
const only = (p, expression) => restriction(p, `<owl:allValuesFrom>${expression}</owl:allValuesFrom>`);
const value = (p, n) => restriction(p, `<owl:hasValue rdf:resource="#${n}"/>`);
const cardinality = (p, c, count, kind) => restriction(p,
  `<owl:${kind} rdf:datatype="${xsd}nonNegativeInteger">${count}</owl:${kind}><owl:onClass rdf:resource="#${c}"/>`);
const numericRange = (type, facet, number) => `<rdfs:Datatype><owl:onDatatype rdf:resource="${xsd}${type}"/><owl:withRestrictions rdf:parseType="Collection"><rdf:Description><xsd:${facet} rdf:datatype="${xsd}${type}">${number}</xsd:${facet}></rdf:Description></owl:withRestrictions></rdfs:Datatype>`;
const dataSome = (p, range) => restriction(p, `<owl:someValuesFrom>${range}</owl:someValuesFrom>`);
function extend(tag, name, content) {
  const start = xml.indexOf(`<${tag} rdf:about="#${name}">`);
  if (start < 0) throw new Error(`Missing baseline entity: ${name}`);
  const end = xml.indexOf(`</${tag}>`, start);
  xml = xml.slice(0, end) + content + '\n  ' + xml.slice(end);
}
const subclass = expression => `  <rdfs:subClassOf>${expression}</rdfs:subClassOf>`;
const additions = [];
const defined = (name, expression) => additions.push(`  <owl:Class rdf:about="#${name}"><owl:equivalentClass>${expression}</owl:equivalentClass></owl:Class>`);
const platforms = ['AM4', 'AM5', 'LGA1700'];
for (const name of ['CPU', 'Motherboard']) extend('owl:Class', name,
  [some('hasSocket', 'Socket'), only('hasSocket', ref('Socket'))].map(subclass).join('\n'));
extend('owl:Class', 'Socket', `  <owl:equivalentClass>${group('oneOf', platforms.map(p => ref(`Socket_${p}`)))}</owl:equivalentClass>`);
extend('owl:Class', 'PCConfiguration', [
  some('hasComponent', 'CPU'), some('hasComponent', 'Motherboard'), some('hasComponent', 'PowerSupply'),
  only('hasComponent', union(ref('CPU'), ref('Motherboard'), ref('PowerSupply'))),
  cardinality('hasComponent', 'Component', 3, 'minQualifiedCardinality'),
  cardinality('hasComponent', 'Component', 3, 'maxQualifiedCardinality'),
  restriction('hasPurpose', `<owl:qualifiedCardinality rdf:datatype="${xsd}nonNegativeInteger">1</owl:qualifiedCardinality><owl:onDataRange rdf:resource="#ConfigurationPurpose"/>`)
].map(subclass).join('\n'));

for (const platform of platforms) {
  defined(`${platform}CPU`, and(ref('CPU'), value('hasSocket', `Socket_${platform}`)));
  defined(`${platform}Motherboard`, and(ref('Motherboard'), value('hasSocket', `Socket_${platform}`)));
  defined(`${platform}Configuration`, and(ref('PCConfiguration'),
    some('hasCPU', `${platform}CPU`), some('hasMotherboard', `${platform}Motherboard`)));
}
defined('SocketCompatibleConfiguration', union(...platforms.map(p => ref(`${p}Configuration`))));
defined('EfficientCPU', and(ref('CPU'), dataSome('hasTDP', numericRange('integer', 'maxInclusive', 65))));
defined('HighPowerSupply', and(ref('PowerSupply'), dataSome('hasWattage', numericRange('integer', 'minInclusive', 650))));
defined('EfficientConfiguration', and(ref('PCConfiguration'), some('hasCPU', 'EfficientCPU')));
defined('OfficeConfiguration', and(ref('PCConfiguration'), restriction('hasPurpose', `<owl:hasValue rdf:datatype="${xsd}string">office</owl:hasValue>`)));

const type = name => `    <rdf:type rdf:resource="http://www.w3.org/2002/07/owl#${name}"/>`;
const characteristics = [type('AsymmetricProperty'), type('IrreflexiveProperty')].join('\n');
const ops = [
  ['hasSocket', union(ref('CPU'), ref('Motherboard')), ref('Socket'), 'isSocketOf', false],
  ['hasCPU', ref('PCConfiguration'), ref('CPU'), 'isCPUOf', true],
  ['hasMotherboard', ref('PCConfiguration'), ref('Motherboard'), 'isMotherboardOf', true],
  ['hasPowerSupply', ref('PCConfiguration'), ref('PowerSupply'), 'isPowerSupplyOf', true]
];
for (const [name, domain, range, inverse, component] of ops) {
  extend('owl:ObjectProperty', name, [characteristics, `    <owl:inverseOf rdf:resource="#${inverse}"/>`,
    ...(component ? ['    <rdfs:subPropertyOf rdf:resource="#hasComponent"/>'] : [])].join('\n'));
  additions.push(`  <owl:ObjectProperty rdf:about="#${inverse}">
${type('InverseFunctionalProperty')}
${characteristics}
    <rdfs:domain>${range}</rdfs:domain><rdfs:range>${domain}</rdfs:range>
  </owl:ObjectProperty>`);
}
for (const [name, domain, range, inverse] of [
  ['hasComponent', 'PCConfiguration', 'Component', 'isComponentOf'],
  ['isComponentOf', 'Component', 'PCConfiguration', null]
]) additions.push(`  <owl:ObjectProperty rdf:about="#${name}">
${characteristics}
    <rdfs:domain rdf:resource="#${domain}"/><rdfs:range rdf:resource="#${range}"/>
${inverse ? `    <owl:inverseOf rdf:resource="#${inverse}"/>` : ''}
  </owl:ObjectProperty>`);

additions.push(`  <rdfs:Datatype rdf:about="#PositiveWattage"><owl:equivalentClass>${numericRange('integer', 'minInclusive', 1)}</owl:equivalentClass></rdfs:Datatype>`,
  `  <rdfs:Datatype rdf:about="#NonNegativePrice"><owl:equivalentClass>${numericRange('decimal', 'minInclusive', 0)}</owl:equivalentClass></rdfs:Datatype>`,
  `  <rdfs:Datatype rdf:about="#ConfigurationPurpose">
    <owl:equivalentClass><rdfs:Datatype><owl:oneOf>
      <rdf:Description><rdf:first rdf:datatype="${xsd}string">office</rdf:first><rdf:rest>
        <rdf:Description><rdf:first rdf:datatype="${xsd}string">general</rdf:first><rdf:rest>
          <rdf:Description><rdf:first rdf:datatype="${xsd}string">performance</rdf:first><rdf:rest rdf:resource="http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"/></rdf:Description>
        </rdf:rest></rdf:Description>
      </rdf:rest></rdf:Description>
    </owl:oneOf></rdfs:Datatype></owl:equivalentClass>
  </rdfs:Datatype>`,
  `  <owl:DatatypeProperty rdf:about="#hasPurpose">
${type('FunctionalProperty')}
    <rdfs:domain rdf:resource="#PCConfiguration"/><rdfs:range rdf:resource="#ConfigurationPurpose"/>
  </owl:DatatypeProperty>`);
for (const [name, datatype] of [['hasTDP', 'PositiveWattage'], ['hasWattage', 'PositiveWattage'], ['hasPrice', 'NonNegativePrice']]) {
  const pattern = new RegExp(`(<owl:DatatypeProperty rdf:about="#${name}">[\\s\\S]*?<rdfs:range rdf:resource=")[^"]+("/>)`);
  xml = xml.replace(pattern, `$1#${datatype}$2`);
}
for (const [name, purpose] of [
  ['PC_Office_AM4', 'office'], ['PC_Performance_AM4', 'performance'],
  ['PC_Modern_AM5', 'general'], ['PC_Intel_LGA1700', 'performance']
]) extend('owl:NamedIndividual', name, `  <hasPurpose rdf:datatype="${xsd}string">${purpose}</hasPurpose>`);

xml = xml.replace('</rdf:RDF>', additions.join('\n\n') + '\n</rdf:RDF>');
fs.writeFileSync(path.join(root, 'PC_Builder.owl'), xml, 'utf8');
console.log('Saved PC_Builder.owl: 20 classes, 10 object properties, 4 data properties, 3 custom datatypes, 18 individuals.');
