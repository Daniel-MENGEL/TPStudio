from tpstudio.projects import (
    ExpectedGraphModel,
    ExpectedModelProposalConfidence,
    ExpectedModelProposalSource,
    infer_expected_graph_model,
    snells_laws_teacher_project,
)


def test_proportionality_proposes_through_origin() -> None:
    proposal = infer_expected_graph_model(("Montrer que Y est proportionnel à X.",))
    assert proposal.model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert proposal.confidence is ExpectedModelProposalConfidence.MEDIUM
    assert proposal.source is ExpectedModelProposalSource.STATEMENT
    assert proposal.evidence


def test_affine_word_proposes_affine() -> None:
    proposal = infer_expected_graph_model(("Ajuster les mesures par une fonction affine.",))
    assert proposal.model is ExpectedGraphModel.AFFINE


def test_quadratic_word_proposes_quadratic() -> None:
    proposal = infer_expected_graph_model(("Modéliser par un polynôme de degré 2.",))
    assert proposal.model is ExpectedGraphModel.QUADRATIC


def test_generic_linear_regression_is_ambiguous() -> None:
    proposal = infer_expected_graph_model(("Faire une régression linéaire.",))
    assert proposal.model is None
    assert proposal.confidence is ExpectedModelProposalConfidence.LOW


def test_contradictory_documents_abstain() -> None:
    proposal = infer_expected_graph_model(
        ("Vérifier une relation de proportionnalité.",),
        ("Ajuster par y = a*x+b.",),
    )
    assert proposal.model is None
    assert proposal.source is ExpectedModelProposalSource.STATEMENT_AND_CORRECTION
    assert len(proposal.evidence) == 2


def test_no_evidence_abstains_without_source() -> None:
    proposal = infer_expected_graph_model(("Tracer y en fonction de x.",))
    assert proposal.model is None
    assert proposal.source is ExpectedModelProposalSource.NONE
    assert proposal.evidence == ()


def test_same_explicit_model_in_statement_and_correction_is_high_confidence() -> None:
    proposal = infer_expected_graph_model(
        ("La relation est proportionnelle.",),
        ("La droite passe par l'origine.",),
    )
    assert proposal.model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert proposal.confidence is ExpectedModelProposalConfidence.HIGH


def test_inference_does_not_mutate_existing_project_contract() -> None:
    project = snells_laws_teacher_project()
    graph = project.graph_expectation_set.get("regression_graph")
    before = graph.expected_model
    infer_expected_graph_model(("Ajuster par une fonction affine.",))
    assert graph.expected_model is before is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN


def test_negated_models_are_not_proposals() -> None:
    for text in (
        "Ne pas utiliser une régression affine.",
        "La relation n'est pas affine.",
        "Y n'est pas proportionnel à X.",
        "Le modèle n'est pas quadratique.",
    ):
        assert infer_expected_graph_model((text,)).model is None


def test_negation_is_local_to_its_segment() -> None:
    proposal = infer_expected_graph_model(("Ne pas oublier les unités. Utiliser une fonction affine.",))
    assert proposal.model is ExpectedGraphModel.AFFINE


def test_exploratory_questions_abstain() -> None:
    assert infer_expected_graph_model(("On vérifiera si une parabole convient ou non.",)).model is None
    assert infer_expected_graph_model(("Tester si une fonction affine convient.",)).model is None


def test_se_demander_si_is_exploratory() -> None:
    for text in (
        "On se demande si Y est proportionnel à X.",
        "On peut se demander si Y est proportionnel à X.",
        "On pourrait se demander si la relation est affine.",
        "Il est possible de se demander si le modèle est quadratique.",
    ):
        proposal = infer_expected_graph_model((text,))
        assert proposal.model is None
        assert proposal.confidence is ExpectedModelProposalConfidence.LOW
        assert proposal.source is ExpectedModelProposalSource.NONE
        assert proposal.evidence == ()


def test_se_demander_si_does_not_neutralize_later_affirmation() -> None:
    proposal = infer_expected_graph_model(
        ("On peut se demander si une relation affine conviendrait. On adopte finalement une fonction affine.",)
    )
    assert proposal.model is ExpectedGraphModel.AFFINE


def test_affirmative_modeling_remains_positive() -> None:
    assert infer_expected_graph_model(("Modéliser par une fonction affine.",)).model is ExpectedGraphModel.AFFINE
    assert infer_expected_graph_model(("Modéliser les points par une parabole.",)).model is ExpectedGraphModel.QUADRATIC


def test_verify_without_question_can_remain_a_positive_instruction() -> None:
    proposal = infer_expected_graph_model(("Vérifier la relation de proportionnalité entre Y et X.",))
    assert proposal.model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert infer_expected_graph_model(("Vérifier si Y est proportionnel à X.",)).model is None


def test_internal_conflict_does_not_use_last_match() -> None:
    proposal = infer_expected_graph_model(
        ("La relation semble proportionnelle.\nOn adopte finalement un modèle affine.",)
    )
    assert proposal.model is None
    assert proposal.confidence is ExpectedModelProposalConfidence.LOW


def test_latex_spacing_variants_are_supported() -> None:
    assert infer_expected_graph_model((r"$y = a\,x$",)).model is ExpectedGraphModel.LINEAR_THROUGH_ORIGIN
    assert infer_expected_graph_model((r"$y = a\,x+b$",)).model is ExpectedGraphModel.AFFINE


def test_silent_documents_have_no_source() -> None:
    proposal = infer_expected_graph_model(("Tracer les points.",), ("Effectuer une régression.",))
    assert proposal.model is None
    assert proposal.source is ExpectedModelProposalSource.NONE
    assert proposal.evidence == ()
