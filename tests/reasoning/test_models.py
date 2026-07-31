from tpstudio.reasoning import Condition, Diagnostic, Fact, Location, Rule

def test_models():
    loc=Location(1)
    fact=Fact("indice",1.49,"calcul",loc)
    cond=Condition("indice",">",1.0)
    rule=Rule("SCI001","Test",[cond])
    diag=Diagnostic("SCI001","OK","SCI001",loc)
    assert fact.location==loc
    assert rule.conditions[0]==cond
    assert diag.rule_id=="SCI001"
