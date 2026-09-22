import java.io.File;
import java.math.BigDecimal;
import java.util.*;
import java.util.stream.Collectors;
import org.semanticweb.owlapi.apibinding.OWLManager;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.profiles.OWL2DLProfile;
import org.semanticweb.owlapi.profiles.OWLProfileReport;
import org.semanticweb.owlapi.reasoner.*;
import org.semanticweb.HermiT.ReasonerFactory;

public class VerifyOntology {
  static final String NS="https://example.org/pc-builder#";
  static OWLDataFactory df;
  static OWLOntology o;
  static OWLOntologyManager manager;
  static OWLClass cls(String n){return df.getOWLClass(IRI.create(NS+n));}
  static OWLNamedIndividual ind(String n){return df.getOWLNamedIndividual(IRI.create(NS+n));}
  static OWLObjectProperty op(String n){return df.getOWLObjectProperty(IRI.create(NS+n));}
  static OWLDataProperty dp(String n){return df.getOWLDataProperty(IRI.create(NS+n));}
  static void check(boolean value,String text){System.out.println((value?"PASS ":"FAIL ")+text);if(!value)throw new IllegalStateException(text);}
  static String names(Collection<? extends OWLEntity> items){return items.stream().map(x->x.getIRI().getShortForm()).sorted().collect(Collectors.joining(", "));}
  static OWLNamedIndividual object(OWLNamedIndividual n,String p){
    Set<OWLIndividual> values=new HashSet<>();
    for(OWLObjectPropertyAssertionAxiom a:o.getObjectPropertyAssertionAxioms(n))if(a.getProperty().equals(op(p)))values.add(a.getObject());
    check(values.size()==1,n.getIRI().getShortForm()+" has exactly one explicit "+p);
    return values.iterator().next().asOWLNamedIndividual();
  }
  static BigDecimal number(OWLNamedIndividual n,String p){
    Set<OWLLiteral> values=new HashSet<>();
    for(OWLDataPropertyAssertionAxiom a:o.getDataPropertyAssertionAxioms(n))if(a.getProperty().equals(dp(p)))values.add(a.getObject());
    check(values.size()==1,n.getIRI().getShortForm()+" has exactly one explicit "+p);
    return new BigDecimal(values.iterator().next().getLiteral());
  }
  static void negativeTest(String label,Set<OWLAxiom> add,Set<OWLAxiom> remove)throws Exception{
    Set<OWLAxiom> axioms=new HashSet<>(o.getAxioms());axioms.removeAll(remove);axioms.addAll(add);
    OWLOntology test=manager.createOntology(axioms);
    OWLReasoner r=new ReasonerFactory().createReasoner(test);
    try{check(!r.isConsistent(),"NEGATIVE CONTROL detected: "+label);}finally{r.dispose();manager.removeOntology(test);}
  }
  public static void main(String[]args)throws Exception{
    manager=OWLManager.createOWLOntologyManager();df=manager.getOWLDataFactory();
    o=manager.loadOntologyFromOntologyDocument(new File(args[0]));
    System.out.println("File: "+new File(args[0]).getCanonicalPath());
    System.out.println("OWLAPI: "+OWLManager.class.getPackage().getImplementationVersion());
    System.out.println("Run: "+java.time.OffsetDateTime.now());
    check(o.getClassesInSignature().size()==20,"20 named domain classes");
    check(o.getObjectPropertiesInSignature().size()==10,"10 object properties");
    check(o.getDataPropertiesInSignature().size()==4,"4 data properties");
    check(o.getIndividualsInSignature().size()==18,"18 named individuals (minimum 12)");
    check(o.getAxiomCount(AxiomType.OBJECT_PROPERTY_ASSERTION)==20,"20 explicit object-property assertions");
    check(o.getAxiomCount(AxiomType.DATA_PROPERTY_ASSERTION)==22,"22 explicit data-property assertions");
    OWLProfileReport profile=new OWL2DLProfile().checkOntology(o);
    check(profile.isInProfile(),"OWL 2 DL profile; violations="+profile.getViolations().size());
    OWLReasoner r=new ReasonerFactory().createReasoner(o);
    System.out.println("Reasoner: "+r.getReasonerName()+" "+r.getReasonerVersion());
    check(r.isConsistent(),"Ontology is consistent");
    r.precomputeInferences(InferenceType.CLASS_HIERARCHY,InferenceType.CLASS_ASSERTIONS,InferenceType.OBJECT_PROPERTY_ASSERTIONS);
    check(r.getUnsatisfiableClasses().getEntitiesMinusBottom().isEmpty(),"No unsatisfiable named classes (excluding owl:Nothing)");
    for(String c:List.of("Component","CPU","Motherboard","PowerSupply","Socket","PCConfiguration")){
      Set<OWLNamedIndividual> instances=r.getInstances(cls(c),false).getFlattened();
      check(!instances.isEmpty(),c+" is populated; inferred instances="+instances.size());
      System.out.println("  "+c+": "+names(instances));
    }
    check(r.getInstances(cls("Component"),false).getFlattened().size()==11,"11 inferred Component instances");
    check(r.getSubClasses(cls("Component"),true).getFlattened().containsAll(List.of(cls("CPU"),cls("Motherboard"),cls("PowerSupply"))),"Component hierarchy inferred correctly");
    check(o.getObjectPropertyDomainAxioms(op("hasSocket")).size()==1 && o.getObjectPropertyDomainAxioms(op("hasSocket")).iterator().next().getDomain().equals(df.getOWLObjectUnionOf(cls("CPU"),cls("Motherboard"))),"hasSocket has one UNION domain: CPU or Motherboard");
    for(OWLNamedIndividual cpu:r.getInstances(cls("CPU"),false).getFlattened()){
      object(cpu,"hasSocket");check(number(cpu,"hasTDP").signum()>0,"Positive CPU TDP");
      check(!r.getTypes(cpu,false).containsEntity(cls("Motherboard")),"CPU not inferred as Motherboard");
    }
    for(OWLNamedIndividual mb:r.getInstances(cls("Motherboard"),false).getFlattened())object(mb,"hasSocket");
    for(OWLNamedIndividual psu:r.getInstances(cls("PowerSupply"),false).getFlattened())check(number(psu,"hasWattage").signum()>0,"Positive PSU Wattage");
    for(OWLNamedIndividual comp:r.getInstances(cls("Component"),false).getFlattened())check(number(comp,"hasPrice").signum()>=0,"Nonnegative component price");
    System.out.println("\nDATA CHECKS (procedural, not OWL entailments; only the simplified assignment criteria)");
    for(OWLNamedIndividual pc:r.getInstances(cls("PCConfiguration"),false).getFlattened().stream().sorted().collect(Collectors.toList())){
      OWLNamedIndividual cpu=object(pc,"hasCPU"),mb=object(pc,"hasMotherboard"),psu=object(pc,"hasPowerSupply");
      OWLNamedIndividual cpuSocket=object(cpu,"hasSocket"),mbSocket=object(mb,"hasSocket");
      BigDecimal tdp=number(cpu,"hasTDP"),wattage=number(psu,"hasWattage");
      BigDecimal price=number(cpu,"hasPrice").add(number(mb,"hasPrice")).add(number(psu,"hasPrice"));
      check(cpuSocket.equals(mbSocket),pc.getIRI().getShortForm()+": CPU and motherboard socket match");
      check(wattage.compareTo(tdp)>=0,pc.getIRI().getShortForm()+": PSU Wattage >= CPU TDP");
      System.out.println("RESULT "+pc.getIRI().getShortForm()+" | socket="+cpuSocket.getIRI().getShortForm()+" | TDP="+tdp+" W | Wattage="+wattage+" W | total="+price+" fictional units");
    }
    VerifyPractice3.verify(o,r,manager,new File(args[0]).getParentFile());
    r.dispose();
    System.out.println("\nNEGATIVE CONTROLS: temporary in-memory copies; final OWL is never modified.");
    negativeTest("CPU asserted as disjoint Motherboard",Set.of(df.getOWLClassAssertionAxiom(cls("Motherboard"),ind("CPU_AM4_65W"))),Set.of());
    negativeTest("Two distinct sockets on a functional property",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasSocket"),ind("CPU_AM4_65W"),ind("Socket_AM5"))),Set.of());
    negativeTest("Two separate hasSocket domains create an intersection",Set.of(df.getOWLObjectPropertyDomainAxiom(op("hasSocket"),cls("CPU")),df.getOWLObjectPropertyDomainAxiom(op("hasSocket"),cls("Motherboard"))),new HashSet<>(o.getObjectPropertyDomainAxioms(op("hasSocket"))));
    negativeTest("Text instead of integer TDP",Set.of(df.getOWLDataPropertyAssertionAxiom(dp("hasTDP"),ind("CPU_AM4_65W"),df.getOWLLiteral("sixty-five"))),Set.of());
    System.out.println("\nALL CHECKS PASSED. HermiT was executed outside the Protege GUI using its installed libraries.");
  }
}
