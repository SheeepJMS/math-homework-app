/**
 * 具体竞赛候选项（用于新建试卷时 autocomplete）
 * 按大类筛选，不含年份，年级/组别用数字表示
 */
var CONTEST_NAMES = [
  "Gauss 7", "Gauss 8", "Pascal", "Cayley", "Fermat", "Euclid",
  "Fryer", "Galois", "Hypatia", "CIMC", "CSMC", "COMC", "CTMC", "Team Up",
  "AMC 8", "AMC 10A", "AMC 10B", "AMC 12A", "AMC 12B", "AIME I", "AIME II", "USAJMO", "USAMO",
  "ELMACON 5 笔试", "ELMACON 5 竞答", "ELMACON 6 笔试", "ELMACON 6 竞答", "ELMACON 7 笔试", "ELMACON 7 竞答",
  "Math Challengers 8 笔试", "Math Challengers 8 竞答", "Math Challengers 9 笔试", "Math Challengers 9 竞答", "Math Challengers 10 笔试", "Math Challengers 10 竞答"
];

/** 大类 → 具体竞赛列表（与表单 category 的 value 一致） */
var CONTEST_BY_CATEGORY = {
  "滑铁卢数学竞赛": [
    "Gauss 7", "Gauss 8", "Pascal", "Cayley", "Fermat", "Euclid",
    "Fryer", "Galois", "Hypatia", "CIMC", "CSMC", "COMC", "CTMC", "Team Up"
  ],
  "AMC美国数学竞赛": [
    "AMC 8", "AMC 10A", "AMC 10B", "AMC 12A", "AMC 12B", "AIME I", "AIME II", "USAJMO", "USAMO"
  ],
  "UBC数学竞赛": [
    "ELMACON 5 笔试", "ELMACON 5 竞答", "ELMACON 6 笔试", "ELMACON 6 竞答", "ELMACON 7 笔试", "ELMACON 7 竞答",
    "Math Challengers 8 笔试", "Math Challengers 8 竞答", "Math Challengers 9 笔试", "Math Challengers 9 竞答", "Math Challengers 10 笔试", "Math Challengers 10 竞答"
  ]
};
