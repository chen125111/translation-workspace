# Translation Workspace

翻译工作空间 — 所有翻译项目的统一处理中心。

## 目录结构

```
translation-workspace/
├── projects/           # 每个翻译项目一个子目录
│   └── example-project/
│       ├── source/     # 源文件（SDLXLIFF、DOCX、TXT 等）
│       ├── batches/    # 分批提取的待翻译内容
│       ├── output/     # 翻译结果
│       └── final/      # 最终交付文件
├── tools/              # 翻译辅助脚本
│   └── split_sdlxliff.py
├── glossary/           # 术语表（跨项目共享）
│   └── technical_terms.json
└── README.md
```

## 使用方式

1. Cursor Agent 在此仓库上运行翻译任务
2. 源文件放入 `projects/<项目名>/source/`
3. Agent 自动拆分、翻译、输出到 `output/`
4. 完成后创建 PR 供审核

## 翻译流程

1. **上传**: 源文件放入 source/
2. **拆分**: 大文件自动拆成小批次（每批 50 段）
3. **翻译**: Cursor Agent 按批次翻译
4. **合并**: 翻译结果合并回原格式
5. **审核**: 创建 PR，人工审核后合并
