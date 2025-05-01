import pandas as pd

# 创建示例数据
data = {
    '题目': [
        '1+1等于几？\nA. 1\nB. 2\nC. 3\nD. 4',
        '中国的首都是？\nA. 上海\nB. 北京\nC. 广州\nD. 深圳',
        '以下哪个是水果？\nA. 胡萝卜\nB. 土豆\nC. 苹果\nD. 白菜',
        '太阳从哪个方向升起？\nA. 东方\nB. 西方\nC. 南方\nD. 北方',
        '水的化学式是？\nA. CO2\nB. O2\nC. H2\nD. H2O'
    ],
    '答案': ['B', 'B', 'C', 'A', 'D'],
    '解析': [
        '1+1=2，这是最基本的加法运算',
        '北京是中国的首都，位于华北地区',
        '苹果是水果，其他选项都是蔬菜',
        '太阳从东方升起，这是自然规律',
        '水的化学式是H2O，由两个氢原子和一个氧原子组成'
    ]
}

# 创建DataFrame
df = pd.DataFrame(data)

# 保存为Excel文件
df.to_excel('示例题目.xlsx', index=False)
print('示例Excel文件已创建：示例题目.xlsx') 