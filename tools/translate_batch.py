#!/usr/bin/env python3
"""
批次翻译工具 — 翻译一个 JSON 批次文件中的所有段落

设计用于 Cursor Agent 在仓库内运行，也可独立使用。

用法:
  python3 translate_batch.py <batch_file.json> <output_file.json> \
    --source-lang en --target-lang zh-CN \
    [--glossary glossary.json]

当通过 Cursor Agent 运行时，Agent 会:
1. 读取 batches/ 目录下的批次文件
2. 翻译每个段落
3. 将结果写入 output/ 目录
4. 提交并创建 PR
"""

import json
import os
import sys
import argparse


def load_glossary(glossary_path):
    """加载术语表"""
    if not glossary_path or not os.path.exists(glossary_path):
        return {}
    with open(glossary_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def format_translation_prompt(segments, source_lang, target_lang, glossary=None):
    """
    生成翻译提示。这个提示会作为 Cursor Agent 的任务描述，
    或者直接用于 LLM API 调用。
    """
    glossary_section = ""
    if glossary:
        terms = "\n".join([f"  - {k} → {v}" for k, v in glossary.items()])
        glossary_section = f"\n术语表（必须遵守）:\n{terms}\n"
    
    segments_text = ""
    for seg in segments:
        segments_text += f'\n[ID: {seg["id"]}]\n{seg["source"]}\n'
    
    prompt = f"""你是专业翻译。请将以下内容从 {source_lang} 翻译为 {target_lang}。
{glossary_section}
要求:
1. 翻译要准确、自然、通顺
2. 保持原文的格式和段落结构
3. 术语表中的词必须按指定翻译
4. 对每个段落，输出格式为: [ID: xxx] 后跟翻译内容
5. 不要添加解释或注释，只输出翻译

待翻译内容:
{segments_text}
"""
    return prompt


def create_agent_task(batch_path, output_path, source_lang, target_lang, glossary=None):
    """
    生成 Cursor Agent 的任务描述文件。
    Agent 读取此文件后，可以直接在仓库中完成翻译。
    """
    with open(batch_path, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    segments = batch_data['segments']
    prompt = format_translation_prompt(segments, source_lang, target_lang, glossary)
    
    task = {
        'description': f"翻译批次 {batch_data['batch_number']}/{batch_data['total_batches']}",
        'input_file': batch_path,
        'output_file': output_path,
        'prompt': prompt,
        'expected_output_format': {
            'batch_number': batch_data['batch_number'],
            'translations': [
                {'id': 'segment_id', 'source': '原文', 'target': '译文'}
            ]
        }
    }
    
    return task


def generate_cursor_agent_command(batch_path, output_path, source_lang, target_lang, 
                                   repo, model="gpt-5.2", glossary=None, no_wait=False):
    """
    生成用于调用 cursor_agent.py 的完整命令。
    小爪可以直接执行这个命令。
    """
    with open(batch_path, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    glossary_data = load_glossary(glossary)
    prompt = format_translation_prompt(batch_data['segments'], source_lang, target_lang, glossary_data)
    
    # 构建 Agent 任务描述
    task_desc = (
        f"翻译任务：将 {batch_path} 中的内容从 {source_lang} 翻译为 {target_lang}。\n\n"
        f"步骤：\n"
        f"1. 读取文件 {batch_path}\n"
        f"2. 翻译每个段落的 source 字段\n"
        f"3. 将翻译结果写入 {output_path}，格式为 JSON，包含 translations 数组\n"
        f"4. 每个翻译条目包含 id、source（原文）和 target（译文）字段\n\n"
        f"{prompt}"
    )
    
    cmd = (
        f'python3 /home/cc/.openclaw/workspace/cursor_agent.py run '
        f'--task "{task_desc[:500]}" '
        f'--repo "{repo}" '
        f'--model {model}'
    )
    
    if no_wait:
        cmd += ' --no-wait'
    else:
        cmd += ' --create-pr'
    
    return cmd


def main():
    parser = argparse.ArgumentParser(description='批次翻译工具')
    parser.add_argument('batch_file', help='输入批次 JSON 文件')
    parser.add_argument('output_file', help='输出翻译结果 JSON 文件')
    parser.add_argument('--source-lang', default='en', help='源语言（默认: en）')
    parser.add_argument('--target-lang', default='zh-CN', help='目标语言（默认: zh-CN）')
    parser.add_argument('--glossary', help='术语表 JSON 文件')
    parser.add_argument('--generate-command', action='store_true',
                       help='生成 cursor_agent.py 调用命令（不执行翻译）')
    parser.add_argument('--repo', default='https://github.com/chen125111/translation-workspace',
                       help='GitHub 仓库地址')
    parser.add_argument('--model', default='gpt-5.2', help='Cursor 模型')
    parser.add_argument('--no-wait', action='store_true', help='不等待完成')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.batch_file):
        print(f"错误: 文件不存在: {args.batch_file}", file=sys.stderr)
        sys.exit(1)
    
    glossary = load_glossary(args.glossary) if args.glossary else None
    
    if args.generate_command:
        cmd = generate_cursor_agent_command(
            args.batch_file, args.output_file,
            args.source_lang, args.target_lang,
            args.repo, args.model, args.glossary, args.no_wait
        )
        print(cmd)
    else:
        task = create_agent_task(
            args.batch_file, args.output_file,
            args.source_lang, args.target_lang, glossary
        )
        print(json.dumps(task, ensure_ascii=False, indent=2))
        print(f"\n✅ 任务文件已生成")
        print(f"   输入: {args.batch_file}")
        print(f"   输出: {args.output_file}")
        print(f"   段落数: {len(json.load(open(args.batch_file))['segments'])}")


if __name__ == '__main__':
    main()
