import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.stream.*;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.formats.RDFXMLDocumentFormat;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.profiles.OWL2DLProfile;
import org.semanticweb.owlapi.reasoner.*;
import org.semanticweb.owlapi.reasoner.structural.StructuralReasonerFactory;
import org.semanticweb.HermiT.ReasonerFactory;
import org.protege.editor.owl.rdf.SparqlResultSet;
import org.protege.editor.owl.rdf.repository.BasicSparqlReasoner;
import org.semanticweb.owlapi.sparql.parser.SPARQLParserImpl;
import org.semanticweb.owlapi.sparql.parser.tokenizer.impl.SPARQLTokenizerJavaCCImpl;
import org.semanticweb.owlapi.sparql.sparqldl.SPARQLDLQueryEngine;
import org.semanticweb.owlapi.sparql.api.*;
import de.derivo.sparqldlapi.QueryEngine;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;

public class Practice5 {
 static final String NS="https://example.org/pc-builder#";
 static void check(boolean b,String s){System.out.println((b?"PASS ":"FAIL ")+s);if(!b)throw new AssertionError(s);}
 static class Result {
  public List<String> columns=new ArrayList<>();
  public List<List<String>> rows=new ArrayList<>();
 }
 static String render(Object x){
  if(x==null)return "";
  if(x instanceof OWLEntity)return ((OWLEntity)x).getIRI().getShortForm();
  if(x instanceof OWLLiteral)return ((OWLLiteral)x).getLiteral();
  if(x instanceof org.openrdf.model.URI)return ((org.openrdf.model.URI)x).getLocalName();
  if(x instanceof org.openrdf.model.Literal)return ((org.openrdf.model.Literal)x).getLabel();
  return x.toString().replace(NS,"");
 }
 static Result standard(BasicSparqlReasoner e,String query)throws Exception{
  SparqlResultSet x=e.executeQuery(query);Result r=new Result();
  for(int c=0;c<x.getColumnCount();c++)r.columns.add(x.getColumnName(c));
  for(int row=0;row<x.getRowCount();row++){List<String>line=new ArrayList<>();for(int c=0;c<x.getColumnCount();c++)line.add(render(x.getResult(row,c)));r.rows.add(line);}return r;
 }
 static Result snap(SPARQLDLQueryEngine e,OWLOntology o,String query){
  SPARQLParserImpl parser=new SPARQLParserImpl(new SPARQLTokenizerJavaCCImpl(o,new StringReader(query)));
  SPARQLQueryResult x=e.ask(parser.parseQuery().asSelectQuery());Result r=new Result();
  for(Variable v:x.getVariables())r.columns.add(v.getName());
  for(int row=0;row<x.getSize();row++){List<String>line=new ArrayList<>();SolutionMapping b=x.getBindingAt(row);for(Variable v:x.getVariables()){
    java.util.Optional<RDFTerm> term=b.getTermForVariable(v);
    if(!term.isPresent())line.add("");else if(term.get() instanceof AtomicIRI)line.add(((AtomicIRI)term.get()).getIRI().getShortForm());else if(term.get() instanceof org.semanticweb.owlapi.sparql.api.Literal)line.add(((org.semanticweb.owlapi.sparql.api.Literal)term.get()).getLexicalForm());else line.add(term.get().toString());
  }r.rows.add(line);}return r;
 }
 static void saveOntology(OWLOntologyManager m,OWLOntology o,Path p)throws Exception{
  RDFXMLDocumentFormat f=new RDFXMLDocumentFormat();f.setDefaultPrefix(NS);m.saveOntology(o,f,IRI.create(p.toFile()));String s=Files.readString(p).replaceAll("(?s)<!--.*?-->","").replaceAll("\\n[ \\t]*(?:\\n[ \\t]*){2,}","\n\n");Files.writeString(p,s.trim()+"\n");
 }
 static String csv(String s){return "\""+s.replace("\"","\"\"")+"\"";}
 static void csv(Result r,Path p)throws Exception{List<String> lines=new ArrayList<>();lines.add(r.columns.stream().map(Practice5::csv).collect(Collectors.joining(",")));for(List<String>line:r.rows)lines.add(line.stream().map(Practice5::csv).collect(Collectors.joining(",")));Files.write(p,lines);}
 static Set<String> semanticRows(Result r,Set<String>ignore){Set<String>out=new HashSet<>();for(List<String>line:r.rows){List<String>parts=new ArrayList<>();for(int j=0;j<r.columns.size();j++){if(ignore.contains(r.columns.get(j)))continue;String value=line.get(j);try{value=new java.math.BigDecimal(value).round(new java.math.MathContext(12)).stripTrailingZeros().toPlainString();}catch(NumberFormatException x){}parts.add(r.columns.get(j)+"="+value);}Collections.sort(parts);out.add(String.join("|",parts));}return out;}
 public static void main(String[]args)throws Exception{
  Path source=Path.of(args[0]),root=Path.of(args[1]);OWLOntologyManager m=OWLManager.createOWLOntologyManager();OWLOntology o=m.loadOntologyFromOntologyDocument(source.toFile());OWLDataFactory d=m.getOWLDataFactory();
  check(o.getAxiomCount(AxiomType.SWRL_RULE)==6,"practice4 source contains six SWRL rules");m.removeAxioms(o,new HashSet<>(o.getAxioms(AxiomType.SWRL_RULE)));
  m.removeAxioms(o,o.getAxioms(AxiomType.DECLARATION).stream().filter(a->a.getEntity().isOWLAnnotationProperty()).collect(Collectors.toSet()));
  m.applyChange(new SetOntologyID(o,new OWLOntologyID(IRI.create("https://example.org/pc-builder/practice5/asserted"))));
  check(new OWL2DLProfile().checkOntology(o).isInProfile(),"asserted projection is OWL 2 DL");saveOntology(m,o,root.resolve("PC_Builder_Asserted.owl"));
  OWLReasoner hermit=new ReasonerFactory().createReasoner(o);check(hermit.isConsistent(),"HermiT source consistency");hermit.precomputeInferences(InferenceType.CLASS_ASSERTIONS,InferenceType.OBJECT_PROPERTY_ASSERTIONS);
  Set<OWLAxiom>closure=new HashSet<>(o.getAxioms());List<String>delta=new ArrayList<>();
  for(OWLNamedIndividual n:o.getIndividualsInSignature()){
   for(OWLClass c:hermit.getTypes(n,false).getFlattened())if(!c.isOWLThing()){OWLAxiom a=d.getOWLClassAssertionAxiom(c,n);if(closure.add(a))delta.add(n.getIRI().getShortForm()+"\trdf:type\t"+c.getIRI().getShortForm());}
   for(OWLObjectProperty p:o.getObjectPropertiesInSignature())for(OWLNamedIndividual v:hermit.getObjectPropertyValues(n,p).getFlattened()){OWLAxiom a=d.getOWLObjectPropertyAssertionAxiom(p,n,v);if(closure.add(a))delta.add(n.getIRI().getShortForm()+"\t"+p.getIRI().getShortForm()+"\t"+v.getIRI().getShortForm());}
  }
  Collections.sort(delta);List<String>deltaFile=new ArrayList<>();deltaFile.add("subject\tpredicate\tobject");deltaFile.addAll(delta);Files.write(root.resolve("results/new-triples.tsv"),deltaFile);
  OWLOntologyManager im=OWLManager.createOWLOntologyManager();OWLOntology inferred=im.createOntology(closure,IRI.create("https://example.org/pc-builder/practice5/inferred"));saveOntology(im,inferred,root.resolve("PC_Builder_Inferred.owl"));
  check(new OWL2DLProfile().checkOntology(inferred).isInProfile(),"inferred materialization is OWL 2 DL");OWLReasoner freshCheck=new ReasonerFactory().createReasoner(inferred);check(freshCheck.isConsistent(),"materialized ontology is consistent");freshCheck.dispose();
  BasicSparqlReasoner basic=new BasicSparqlReasoner(m);basic.precalculate();BasicSparqlReasoner materialized=new BasicSparqlReasoner(im);materialized.precalculate();OWLReasoner snapshotReasoner=new StructuralReasonerFactory().createReasoner(inferred);SPARQLDLQueryEngine snapEngine=new SPARQLDLQueryEngine(d,QueryEngine.create(im,snapshotReasoner));
  Map<String,Object> report=new LinkedHashMap<>();report.put("assertedObjectAssertions",o.getAxiomCount(AxiomType.OBJECT_PROPERTY_ASSERTION));report.put("inferredObjectAssertions",inferred.getAxiomCount(AxiomType.OBJECT_PROPERTY_ASSERTION));report.put("assertedClassAssertions",o.getAxiomCount(AxiomType.CLASS_ASSERTION));report.put("inferredClassAssertions",inferred.getAxiomCount(AxiomType.CLASS_ASSERTION));report.put("newNamedFacts",delta.size());report.put("source","practice4/"+source.getFileName().toString());report.put("inferenceReasoner",hermit.getReasonerName()+" "+hermit.getReasonerVersion());report.put("snapReasoner","Structural over materialized HermiT named facts");
  Map<String,Object> queries=new LinkedHashMap<>();int[] assertedCounts={4,0,4,0,0},inferredCounts={4,1,4,3,4};List<Path>files=Files.list(root.resolve("queries/standard")).filter(p->p.toString().endsWith(".rq")).sorted().collect(Collectors.toList());check(files.size()==5,"five SELECT queries");
  for(int j=0;j<files.size();j++){
   Path qpath=files.get(j);String query=Files.readString(qpath);String key=qpath.getFileName().toString().replace(".rq","");String snapQuery=Files.readString(root.resolve("queries/snap").resolve(qpath.getFileName()));Result a=standard(basic,query),b=snap(snapEngine,inferred,snapQuery),z=standard(materialized,query);
   System.out.println("QUERY "+key+" asserted="+a.rows.size()+" inferred="+b.rows.size());System.out.println("ASSERTED "+a.columns+" "+a.rows);System.out.println("SNAP "+b.columns+" "+b.rows);
   check(a.rows.size()==assertedCounts[j],key+" asserted row count");check(b.rows.size()==inferredCounts[j],key+" Snap row count");check(semanticRows(b,Set.of("sampleCPU")).equals(semanticRows(z,Set.of("sampleCPU"))),key+" agrees with standard SPARQL over materialized closure");
   if(j==3)for(List<String>line:b.rows){String sample=line.get(b.columns.indexOf("sampleCPU")),socket=line.get(b.columns.indexOf("socket"));OWLNamedIndividual sampleIndividual=d.getOWLNamedIndividual(IRI.create(NS+sample));check(snapshotReasoner.getObjectPropertyValues(sampleIndividual,d.getOWLObjectProperty(IRI.create(NS+"hasSocket"))).containsEntity(d.getOWLNamedIndividual(IRI.create(NS+socket))),"SAMPLE is a member of "+socket);}
   if(j==2){check(a.rows.stream().allMatch(line->line.get(a.columns.indexOf("pc")).isEmpty()),"OPTIONAL preserves all four CPUs without inverse assertions");check(b.rows.stream().allMatch(line->!line.get(b.columns.indexOf("pc")).isEmpty()),"OPTIONAL inverse links are bound after inference");}
   csv(a,root.resolve("results/"+key+"_asserted.csv"));csv(b,root.resolve("results/"+key+"_inferred.csv"));Map<String,Object>entry=new LinkedHashMap<>();entry.put("asserted",a);entry.put("inferred",b);entry.put("materializedCrossCheck",true);queries.put(key,entry);
  }
  String typeError="PREFIX : <"+NS+"> SELECT ?pc WHERE { ?pc a :PCConfiguration ; :hasPurpose ?purpose . FILTER (?purpose > 300) }";
  Result ta=standard(basic,typeError),tb=snap(snapEngine,inferred,typeError);check(ta.rows.isEmpty()&&tb.rows.isEmpty(),"incompatible string/number FILTER rejects rows in both engines");report.put("typeErrorFilterRowsAsserted",ta.rows.size());report.put("typeErrorFilterRowsInferred",tb.rows.size());report.put("queries",queries);
  new ObjectMapper().enable(SerializationFeature.INDENT_OUTPUT).writeValue(root.resolve("results/results.json").toFile(),report);
  basic.dispose();materialized.dispose();snapshotReasoner.dispose();hermit.dispose();System.out.println("PASS all five queries executed by the real Basic SPARQL and Snap SPARQL engines");
 }
}
