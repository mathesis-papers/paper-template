# 附录 A 齐肯多夫表示与进位

::: {.definition #def-canonical-raw title="规范数字串与它的值" lean="D5/S1/Digit/Raw.CanonicalRaw D5/S1/Digit/Raw.rawValue"}
（待写）
:::

::: {.theorem #thm-zeckendorf-exists title="齐肯多夫表示存在" lean="D5/S1/Digit/Addition.rawValue_toRaw_Z"}
（待写）
:::

::: {.theorem #thm-zeckendorf-unique title="齐肯多夫表示唯一" lean="D5/S1/Digit/Normalize.canonicalRaw_unique"}
（待写）
:::

::: {.proposition #prop-zeckendorf-order title="字典序就是大小" lean="D5/S1/Words/ZeckendorfOrder.zeckendorf_lex_iff_lt"}
（待写）
:::

## 进位 {#sec-carries}

::: {.lemma #lem-carry-value title="进位不改变值" lean="D5/S1/Digit/Carry.rawValue_carryStep"}
（待写）
:::

::: {.theorem #thm-carry-confluent title="进位合流" lean="D5/S1/Digit/CarryStepConfluence.carryStep_confluent"}
（待写）
:::

::: {.theorem #thm-zeck-add title="黄金加法" lean="D5/S1/Digit/Addition.zeck_add"}
（待写）
:::

::: {.lemma #lem-face-invariant title="内部进位在两面上都不花钱" lean="D5/S1/Deficit/GoldenCarryLedger.carry_rewrite_face_invariant"}
（待写）
:::

::: {.theorem #thm-charge-unique title="进位电荷与路径无关" lean="D5/S1/Deficit/ChargedCarryPath.charged_normal_form_unique"}
（待写）
:::
