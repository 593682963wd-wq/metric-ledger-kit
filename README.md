# 精确金额、积分与多源统计账本

作者：Wangyuan · 2026-10-29

本项目源码采用 MIT 许可证，见 LICENSE；第三方依赖仍适用各自上游许可。

## 可用能力

- 显式表头的多XLSX导入、稳定身份回填用户提供的模板，保留未改动单元格公式/样式；中性XLSX导出。
- 十进制金额与精确非负整数，采购目录规格、包装/申请/实收、显式单价上限及汇总；不含供应商。
- 按稳定身份与来源键汇总多指标分值、显式权重/基础值，月份核对、重复去重、冲突拒绝、缺项不填零。
- SQLite积分人工确认、幂等写入、乐观修订与审计、月度覆盖；配置分段及并列排名。
- 已售/容量缺失与零分母区分；价格有效期、证据与单位匹配、精确差额及相对差候选；CSV公式文本转义。

## 运行

Python 3.11+。依赖仅为标准库，或 requirements.txt 明确列出的开源解析库。程序默认不联网；安装依赖时由包管理器下载。

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 -B cli.py demo
python3 -B cli.py demo --output demo-output
python3 -B cli.py run example.json --output demo-output
python3 -B -m unittest discover -s tests -v
```

演示数据从零生成；默认临时目录会在命令结束时释放。需要保留文件或数据库时必须指定 --output，输入与输出目录应由使用者自行控制。JSON输出到标准输出，参数错误返回非零状态。

## 输入与输出

动作：`procurement`、`ratio`、`join`、`rank`、`prices`、`record`、`monthly`、`read_xlsx`、`fill_template`、`export_xlsx`；库接口 `export_csv`。每个动作参数名称对应核心文件中的同名函数/方法签名，公共接口有类型标注及中文说明。通用调用格式是 action 与 args；目录、收集模块另接受 tools/events/contract 等顶层显式合同。

```json
{
  "action": "ratio",
  "args": {
    "sold": 5,
    "capacity": 10
  }
}
```

人员仅为调用方稳定匿名标识，不进行姓名模糊匹配。缺失指标显示已知小计和None总分。价格变动结果始终是candidate，不构成采购决定。分值和货币使用Decimal；超过默认Decimal运算精度的极端金额需要调用方明确设置上下文并重新验证。

## 保留边界

真实人员工号/绩效、业务基础分与层级、购物链接/商品目录/供应商、具体油价和预售数据源、原模板及自动采购/报告发送均未包含。

只保留通用流程与算法；这是经过提取/重构的独立工具或组件集合，并不声称完整迁移原应用、原业务质量或生产验收。源码来源、哈希与原入口映射保存在本地私有审计台账，不随此目录分发。

## 验证

tests/仅使用合成数据与临时文件，覆盖主流程、空/缺失、身份冲突和关键异常；cli.py demo可独立复现完整示例。未运行真实业务数据、联网/正式发送、原系统回归或生产部署。本项目为CLI/库，不包含Web UI。

## 2026-11-08 候选修订

- 日期/时刻单元格转换ISO文本，可被CLI JSON输出。
- 新增audit_changes记录身份/月份/分值旧新值，保留原审计表兼容。
- CSV表头也转义公式前缀。
- samefile拒绝硬链接覆盖模板。
- XLSX表头也转义公式前缀。

使用包内合成样例复跑；发布集合根目录的 `verify_release.py --project workflow-metric-ledger` 会依次执行测试和首次使用命令。原有版本的测试计数属于当时记录，本轮汇总以集合验证报告为准。
