// 诊断报告（专家诊断型）——TypeScript 类型定义（前端/接口对齐用）

export type ErrorType =
  | 'arithmetic_error'
  | 'concept_misunderstanding'
  | 'modeling_error'
  | 'careless_error'
  | 'time_management';

export interface ExpertAbilityLevel {
  level_score: 1 | 2 | 3 | 4 | 5;
  level_label: string; // e.g. 基础待强化 / 中等水平 / 具备竞赛潜力
  predicted_range: null | { low: number; high: number; max: number };
  prep_stage: string; // 建议备赛阶段
  time_stability_score: null | number; // 0~100，越高越稳定
}

export interface Quadrants {
  fast_wrong: number;
  slow_wrong: number;
  fast_correct: number;
  slow_correct: number;
}

export interface ExpertAnswerStyle {
  quadrants: Quadrants;
  style_label: string; // 冲动型 / 稳健型 / 理解困难型 / 熟练型
  calculation_stability: '高' | '中' | '低';
  time_allocation_stability: '高' | '中' | '低';
  descriptions: string[]; // 3条风格描述
}

export interface ExpertErrorTypeStatItem {
  key: ErrorType;
  label: string;
  count: number;
  percent: number; // 0~100
}

export interface ExpertErrorTypeStats {
  total_tagged: number;
  items: ExpertErrorTypeStatItem[];
}

export interface ExpertLearningRisk {
  risk_level: '低' | '中' | '高';
  tone: 'success' | 'warning' | 'danger';
  reasons: string[];
}

export interface ExpertGrowthPotential {
  strength_kps: string[];
  message: string;
}

export interface ExpertDiagnosis {
  ability_level: ExpertAbilityLevel;
  answer_style: ExpertAnswerStyle;
  error_type_stats: null | ExpertErrorTypeStats; // 无数据则隐藏模块
  learning_risk: ExpertLearningRisk;
  growth_potential: null | ExpertGrowthPotential; // 无知识点则隐藏模块
}

// 模拟示例数据（用于营销展示/前端联调）
export const mockExpertDiagnosis: ExpertDiagnosis = {
  ability_level: {
    level_score: 4,
    level_label: '具备竞赛潜力',
    predicted_range: { low: 98, high: 132, max: 150 },
    prep_stage: '套卷训练 + 策略优化，追求稳定高分',
    time_stability_score: 72,
  },
  answer_style: {
    quadrants: { fast_wrong: 3, slow_wrong: 4, fast_correct: 10, slow_correct: 8 },
    style_label: '稳健型',
    calculation_stability: '中',
    time_allocation_stability: '中',
    descriptions: [
      '整体节奏相对均衡，说明你能在速度与正确之间权衡。',
      '建议把慢题拆解为“卡点清单”，逐步降低慢错比例。',
      '通过套卷训练形成固定节奏：先稳拿基础分，再冲高分。',
    ],
  },
  error_type_stats: {
    total_tagged: 10,
    items: [
      { key: 'careless_error', label: '粗心失误', count: 4, percent: 40 },
      { key: 'arithmetic_error', label: '计算失误', count: 3, percent: 30 },
      { key: 'concept_misunderstanding', label: '概念误解', count: 2, percent: 20 },
      { key: 'time_management', label: '时间管理', count: 1, percent: 10 },
    ],
  },
  learning_risk: {
    risk_level: '中',
    tone: 'warning',
    reasons: ['慢+错比例偏高', '空题偏多（>3）'],
  },
  growth_potential: {
    strength_kps: ['数论', '计数'],
    message: '在「数论」与「计数」题型中表现较好，说明逻辑结构理解能力具备基础优势。建议以此为支点，带动薄弱模块提升。',
  },
};

