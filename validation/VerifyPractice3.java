import java.io.File;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.util.*;
import java.util.stream.Collectors;
import org.semanticweb.owlapi.model.*;
import org.semanticweb.owlapi.reasoner.*;
import org.semanticweb.HermiT.ReasonerFactory;

public class VerifyPractice3 extends VerifyOntology {
  static Set<OWLNamedIndividual> individuals(String... names) {
    return Arrays.stream(names).map(VerifyOntology::ind).collect(Collectors.toSet());
  }
  static void instances(OWLReasoner r, String c, String... expected) {
    Set<OWLNamedIndividual> actual=r.getInstances(cls(c),false).getFlattened();
    check(actual.equals(individuals(expected)),"Inferred "+c+" = ["+names(actual)+"]");
  }
  static OWLDataPropertyAssertionAxiom literal(String p,String n,String val,String datatype) {
    return df.getOWLDataPropertyAssertionAxiom(dp(p),ind(n),df.getOWLLiteral(val,df.getOWLDatatype(IRI.create("http://www.w3.org/2001/XMLSchema#"+datatype))));
  }
  static Set<OWLAxiom> dataAssertions(String n,String p) {
    return o.getDataPropertyAssertionAxioms(ind(n)).stream().filter(a->a.getProperty().equals(dp(p))).collect(Collectors.toSet());
  }
  static Set<OWLAxiom> objectAssertions(String n,String p) {
    return o.getObjectPropertyAssertionAxioms(ind(n)).stream().filter(a->a.getProperty().equals(op(p))).collect(Collectors.toSet());
  }
  static void variant(String label,Set<OWLAxiom> add,Set<OWLAxiom> remove,java.util.function.Consumer<OWLReasoner> checks)throws Exception {
    Set<OWLAxiom> axioms=new HashSet<>(o.getAxioms());axioms.removeAll(remove);axioms.addAll(add);
    OWLOntology copy=manager.createOntology(axioms);
    OWLReasoner r=new ReasonerFactory().createReasoner(copy);
    try { check(r.isConsistent(),label+": consistent");checks.accept(r); }
    finally {r.dispose();manager.removeOntology(copy);}
  }
  public static void verify(OWLOntology ontology,OWLReasoner r,OWLOntologyManager m,File root)throws Exception {
    o=ontology;manager=m;df=m.getOWLDataFactory();
    System.out.println("\nPRACTICE 3: FORMAL CONSTRAINTS AND INFERENCES");
    OWLOntology baseline=org.semanticweb.owlapi.apibinding.OWLManager.createOWLOntologyManager()
      .loadOntologyFromOntologyDocument(new File(root,"validation/practice2/PC_Builder.owl"));
    check(o.getIndividualsInSignature().equals(baseline.getIndividualsInSignature()),"All original individuals preserved");
    check(o.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION).equals(baseline.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION)),"Original 20 forward object facts unchanged");
    check(o.getAxioms(AxiomType.DATA_PROPERTY_ASSERTION).containsAll(baseline.getAxioms(AxiomType.DATA_PROPERTY_ASSERTION)),"Original 18 numeric facts preserved");
    check(o.getAxioms(AxiomType.CLASS_ASSERTION).equals(baseline.getAxioms(AxiomType.CLASS_ASSERTION)),"Original individual class assertions unchanged");
    check(o.getAxioms(AxiomType.SUBCLASS_OF).containsAll(baseline.getAxioms(AxiomType.SUBCLASS_OF)),"Original class hierarchy and restrictions preserved");
    for(OWLObjectProperty p:o.getObjectPropertiesInSignature()) {
      check(o.getObjectPropertyDomainAxioms(p).size()==1 && o.getObjectPropertyRangeAxioms(p).size()==1,"Domain and range: "+p.getIRI().getShortForm());
      check(r.isEntailed(df.getOWLAsymmetricObjectPropertyAxiom(p)) && r.isEntailed(df.getOWLIrreflexiveObjectPropertyAxiom(p)),"Asymmetric and irreflexive: "+p.getIRI().getShortForm());
    }
    for(OWLDataProperty p:o.getDataPropertiesInSignature()) {
      check(o.getDataPropertyDomainAxioms(p).size()==1 && o.getDataPropertyRangeAxioms(p).size()==1,"Data domain and range: "+p.getIRI().getShortForm());
      check(r.isEntailed(df.getOWLFunctionalDataPropertyAxiom(p)),"Functional data property: "+p.getIRI().getShortForm());
    }
    check(o.getAxiomCount(AxiomType.DATATYPE_DEFINITION)==3,"Three custom datatype definitions");
    check(o.getAxiomCount(AxiomType.INVERSE_OBJECT_PROPERTIES)==5,"Five inverse-property pairs");
    Set<String> defined=Set.of("AM4CPU","AM5CPU","LGA1700CPU","AM4Motherboard","AM5Motherboard","LGA1700Motherboard","AM4Configuration","AM5Configuration","LGA1700Configuration","SocketCompatibleConfiguration","EfficientCPU","HighPowerSupply","EfficientConfiguration","OfficeConfiguration");
    for(String c:defined) {
      check(!o.getEquivalentClassesAxioms(cls(c)).isEmpty(),"Defined with EquivalentClasses: "+c);
      check(o.getClassAssertionAxioms(cls(c)).isEmpty(),"No manual membership: "+c);
    }
    instances(r,"AM4CPU","CPU_AM4_65W","CPU_AM4_105W");
    instances(r,"AM5CPU","CPU_AM5_65W");instances(r,"LGA1700CPU","CPU_LGA1700_125W");
    instances(r,"AM4Motherboard","Motherboard_AM4_A","Motherboard_AM4_B");
    instances(r,"AM5Motherboard","Motherboard_AM5");instances(r,"LGA1700Motherboard","Motherboard_LGA1700");
    instances(r,"AM4Configuration","PC_Office_AM4","PC_Performance_AM4");
    instances(r,"AM5Configuration","PC_Modern_AM5");instances(r,"LGA1700Configuration","PC_Intel_LGA1700");
    instances(r,"SocketCompatibleConfiguration","PC_Office_AM4","PC_Performance_AM4","PC_Modern_AM5","PC_Intel_LGA1700");
    instances(r,"EfficientCPU","CPU_AM4_65W","CPU_AM5_65W");
    instances(r,"HighPowerSupply","PSU_650W","PSU_750W");
    instances(r,"EfficientConfiguration","PC_Office_AM4","PC_Modern_AM5");
    instances(r,"OfficeConfiguration","PC_Office_AM4");
    for(String platform:List.of("AM4","AM5","LGA1700")) {
      check(r.isEntailed(df.getOWLSubClassOfAxiom(cls(platform+"Configuration"),cls("SocketCompatibleConfiguration"))),"Inferred hierarchy: "+platform+"Configuration < SocketCompatibleConfiguration");
      check(r.isEntailed(df.getOWLSubClassOfAxiom(cls(platform+"CPU"),cls("CPU"))),"Inferred hierarchy: "+platform+"CPU < CPU");
    }
    check(!r.isEntailed(df.getOWLSubClassOfAxiom(cls("PCConfiguration"),cls("SocketCompatibleConfiguration"))),"Socket compatibility is classified from facts, not assumed for every PC");
    check(r.getDisjointClasses(cls("AM4CPU")).containsEntity(cls("AM5CPU")),"Different socket-specific CPU classes inferred disjoint");
    check(r.getDisjointClasses(cls("AM4Configuration")).containsEntity(cls("AM5Configuration")),"Different platform configurations inferred disjoint");
    Set<String> forward=Set.of("hasSocket","hasCPU","hasMotherboard","hasPowerSupply");
    Map<String,String> inverse=Map.of("hasSocket","isSocketOf","hasCPU","isCPUOf","hasMotherboard","isMotherboardOf","hasPowerSupply","isPowerSupplyOf");
    for(OWLObjectPropertyAssertionAxiom a:o.getAxioms(AxiomType.OBJECT_PROPERTY_ASSERTION)) {
      String p=a.getProperty().asOWLObjectProperty().getIRI().getShortForm();
      check(forward.contains(p),"Only forward source assertion: "+p);
      check(r.isEntailed(df.getOWLObjectPropertyAssertionAxiom(op(inverse.get(p)),a.getObject(),a.getSubject())),"Inverse inferred for "+a.getSubject().asOWLNamedIndividual().getIRI().getShortForm()+" / "+p);
    }
    check(r.getObjectPropertyValues(ind("PSU_650W"),op("isPowerSupplyOf")).getFlattened().equals(individuals("PC_Modern_AM5","PC_Performance_AM4")),"One catalog PSU can be used in two configurations");
    check(r.getObjectPropertyValues(ind("Socket_AM4"),op("isSocketOf")).getFlattened().size()==4,"Inverse isSocketOf has four values, not functional");
    for(OWLNamedIndividual pc:r.getInstances(cls("PCConfiguration"),false).getFlattened()) {
      Set<OWLNamedIndividual> expected=new HashSet<>();
      for(String p:List.of("hasCPU","hasMotherboard","hasPowerSupply")) expected.addAll(r.getObjectPropertyValues(pc,op(p)).getFlattened());
      check(r.getObjectPropertyValues(pc,op("hasComponent")).getFlattened().equals(expected) && expected.size()==3,"Exactly three inferred components: "+pc.getIRI().getShortForm());
      for(OWLNamedIndividual comp:expected) check(r.getObjectPropertyValues(comp,op("isComponentOf")).containsEntity(pc),"Generic inverse isComponentOf inferred");
      Set<OWLAxiom> purpose=dataAssertions(pc.getIRI().getShortForm(),"hasPurpose");
      check(purpose.size()==1,"One explicit purpose for "+pc.getIRI().getShortForm());
    }
    List<String> hierarchy=new ArrayList<>(), memberships=new ArrayList<>(), relations=new ArrayList<>();
    for(OWLClass c:o.getClassesInSignature().stream().sorted().collect(Collectors.toList())) {
      hierarchy.add(c.getIRI().getShortForm()+" -> direct parents: "+names(r.getSuperClasses(c,true).getFlattened()));
      memberships.add(c.getIRI().getShortForm()+": "+names(r.getInstances(c,false).getFlattened()));
    }
    for(OWLNamedIndividual n:o.getIndividualsInSignature().stream().sorted().collect(Collectors.toList()))
      for(OWLObjectProperty p:o.getObjectPropertiesInSignature().stream().sorted().collect(Collectors.toList()))
        for(OWLNamedIndividual target:r.getObjectPropertyValues(n,p).getFlattened().stream().sorted().collect(Collectors.toList()))
          relations.add(n.getIRI().getShortForm()+" --"+p.getIRI().getShortForm()+"--> "+target.getIRI().getShortForm());
    check(relations.size()==64,"64 entailed named object relations: 20 original + 44 inferred");
    File output=new File(root,"validation");
    Files.write(output.toPath().resolve("inferred-hierarchy.txt"),hierarchy,StandardCharsets.UTF_8);
    Files.write(output.toPath().resolve("inferred-instances.txt"),memberships,StandardCharsets.UTF_8);
    Files.write(output.toPath().resolve("inferred-relations.txt"),relations,StandardCharsets.UTF_8);

    System.out.println("\nPRACTICE 3: NEGATIVE CONTROLS (IN-MEMORY COPIES)");
    negativeTest("TDP must be positive",Set.of(literal("hasTDP","CPU_AM4_65W","0","integer")),dataAssertions("CPU_AM4_65W","hasTDP"));
    negativeTest("Wattage must be positive",Set.of(literal("hasWattage","PSU_450W","-1","integer")),dataAssertions("PSU_450W","hasWattage"));
    negativeTest("Price must be nonnegative",Set.of(literal("hasPrice","CPU_AM4_65W","-0.01","decimal")),dataAssertions("CPU_AM4_65W","hasPrice"));
    negativeTest("Purpose outside enumeration",Set.of(literal("hasPurpose","PC_Office_AM4","gaming","string")),dataAssertions("PC_Office_AM4","hasPurpose"));
    negativeTest("Two different functional data values",Set.of(literal("hasPurpose","PC_Office_AM4","general","string")),Set.of());
    negativeTest("Fourth distinct component exceeds max 3",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasComponent"),ind("PC_Office_AM4"),ind("CPU_AM4_105W"))),Set.of());
    OWLNamedIndividual extra=ind("UnsupportedComponent");
    Set<OWLAxiom> invalidComponent=new HashSet<>(Set.of(df.getOWLDeclarationAxiom(extra),df.getOWLClassAssertionAxiom(cls("Component"),extra),df.getOWLObjectPropertyAssertionAxiom(op("hasComponent"),ind("PC_Office_AM4"),extra)));
    for(String c:List.of("CPU","Motherboard","PowerSupply")) invalidComponent.add(df.getOWLClassAssertionAxiom(df.getOWLObjectComplementOf(cls(c)),extra));
    Set<OWLAxiom> maxRestrictions=o.getSubClassAxiomsForSubClass(cls("PCConfiguration")).stream().filter(a->a.getSuperClass() instanceof OWLObjectMaxCardinality).collect(Collectors.toSet());
    check(maxRestrictions.size()==1,"One explicit max restriction isolated for only test");
    negativeTest("allValuesFrom excludes other Component kinds",invalidComponent,maxRestrictions);
    OWLNamedIndividual socket=ind("Socket_Unknown");
    Set<OWLAxiom> fourthSocket=new HashSet<>(Set.of(df.getOWLDeclarationAxiom(socket),df.getOWLClassAssertionAxiom(cls("Socket"),socket)));
    for(String known:List.of("Socket_AM4","Socket_AM5","Socket_LGA1700")) fourthSocket.add(df.getOWLDifferentIndividualsAxiom(socket,ind(known)));
    negativeTest("Closed Socket class rejects a fourth distinct socket",fourthSocket,Set.of());
    negativeTest("hasComponent cannot point to Socket",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasComponent"),ind("PC_Office_AM4"),ind("Socket_AM4"))),Set.of());
    negativeTest("Self-link violates irreflexivity",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasCPU"),ind("PC_Office_AM4"),ind("PC_Office_AM4"))),Set.of());
    negativeTest("Second distinct CPU violates exactly 1",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasCPU"),ind("PC_Office_AM4"),ind("CPU_AM4_105W"))),Set.of());
    negativeTest("Explicit zero CPU conflicts with required existence",Set.of(df.getOWLClassAssertionAxiom(df.getOWLObjectMaxCardinality(0,op("hasCPU")),ind("PC_Office_AM4"))),objectAssertions("PC_Office_AM4","hasCPU"));

    System.out.println("\nPRACTICE 3: OPEN-WORLD AND COMPATIBILITY CONTROLS");
    variant("Missing explicit CPU uses open-world semantics",Set.of(),objectAssertions("PC_Office_AM4","hasCPU"),rr->
      check(rr.isEntailed(df.getOWLClassAssertionAxiom(df.getOWLObjectSomeValuesFrom(op("hasCPU"),cls("CPU")),ind("PC_Office_AM4"))),"Required CPU existence is entailed despite missing assertion"));
    variant("Mismatched known sockets",Set.of(df.getOWLObjectPropertyAssertionAxiom(op("hasMotherboard"),ind("PC_Office_AM4"),ind("Motherboard_AM5"))),objectAssertions("PC_Office_AM4","hasMotherboard"),rr-> {
      check(!rr.getInstances(cls("SocketCompatibleConfiguration"),false).containsEntity(ind("PC_Office_AM4")),"Mismatched configuration is not classified compatible");
      check(rr.isEntailed(df.getOWLClassAssertionAxiom(df.getOWLObjectComplementOf(cls("SocketCompatibleConfiguration")),ind("PC_Office_AM4"))),"Mismatched known configuration is entailed NOT socket-compatible");
    });
  }
}
