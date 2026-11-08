# 前言

本书演示 trureturing 书籍模板的写作约定。书中每一条定理、引理、命题与推论，都对应 [trureturing](https://github.com/the-omega-institute/trureturing) 中一条已被 Lean 内核验证并冻结的声明；Lean 代码写在 trureturing 里，本书只按 GID 引用它们。构建时，`./tbook check` 会在所钉的提交上逐条核对冻结状态片，书末的“形式化验证账本”也由构建自动生成。

尚未证明的结论一律写成猜想或开放问题，不冠以定理之名。
