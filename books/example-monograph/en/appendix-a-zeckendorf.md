# Appendix A Zeckendorf representations and carries

::: {.definition #def-canonical-raw title="Canonical digit strings and their value" lean="D5/S1/Digit/Raw.CanonicalRaw D5/S1/Digit/Raw.rawValue"}
(To be written.)
:::

::: {.theorem #thm-zeckendorf-exists title="Zeckendorf representations exist" lean="D5/S1/Digit/Addition.rawValue_toRaw_Z"}
(To be written.)
:::

::: {.theorem #thm-zeckendorf-unique title="Zeckendorf representations are unique" lean="D5/S1/Digit/Normalize.canonicalRaw_unique"}
(To be written.)
:::

::: {.proposition #prop-zeckendorf-order title="Lexicographic order is numeric order" lean="D5/S1/Words/ZeckendorfOrder.zeckendorf_lex_iff_lt"}
(To be written.)
:::

## Carries {#sec-carries}

::: {.lemma #lem-carry-value title="A carry keeps the value" lean="D5/S1/Digit/Carry.rawValue_carryStep"}
(To be written.)
:::

::: {.theorem #thm-carry-confluent title="Carries are confluent" lean="D5/S1/Digit/CarryStepConfluence.carryStep_confluent"}
(To be written.)
:::

::: {.theorem #thm-zeck-add title="Golden addition" lean="D5/S1/Digit/Addition.zeck_add"}
(To be written.)
:::

::: {.lemma #lem-face-invariant title="Internal carries cost nothing on either face" lean="D5/S1/Deficit/GoldenCarryLedger.carry_rewrite_face_invariant"}
(To be written.)
:::

::: {.theorem #thm-charge-unique title="The carry charge does not depend on the path" lean="D5/S1/Deficit/ChargedCarryPath.charged_normal_form_unique"}
(To be written.)
:::
