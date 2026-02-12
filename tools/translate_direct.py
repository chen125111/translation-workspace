#!/usr/bin/env python3
"""
直接调用 DeepSeek API 并行翻译 — 不走 Cursor Agent，速度快 10 倍

用法:
  python3 translate_direct.py <batches_dir> <output_dir> [--workers 13] [--source-lang zh-CN] [--target-lang en-US]
"""

import json
import os
import sys
import argparse
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error


DEEPSEEK_API_KEY = "sk-09f7a4eb0e7e447db57cf5609a93b176"
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def translate_batch(batch_path, output_path, source_lang="zh-CN", target_lang="en-US"):
    """翻译单个批次文件"""
    with open(batch_path, 'r', encoding='utf-8') as f:
        batch_data = json.load(f)
    
    segments = batch_data['segments']
    batch_num = batch_data['batch_number']
    
    # 构建翻译提示
    segments_text = ""
    for seg in segments:
        segments_text += f'[ID: {seg["id"]}]\n{seg["source"]}\n\n'
    
    prompt = f"""你是专业的工程技术文档翻译。请将以下中文内容翻译为英文。

要求：
1. 翻译准确、专业、严谨
2. 这是越南Vinmetal热回收炼焦工程技术方案文档
3. 冶金术语：焦炉=coke oven, 热回收=heat recovery, 炼焦=coking, 装煤=coal charging, 推焦=coke pushing, 熄焦=coke quenching, 干熄焦=dry quenching, 湿熄焦=wet quenching
4. 保持原文编号和格式
5. 输出格式：每段以 [ID: xxx] 开头，后跟英文翻译，段落间空行分隔
6. 不要添加解释或注释

待翻译内容：

{segments_text}"""

    # 调用 DeepSeek API
    request_body = json.dumps({
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a professional engineering document translator specializing in metallurgy and coking technology."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 8192
    }).encode('utf-8')
    
    req = urllib.request.Request(
        DEEPSEEK_API_URL,
        data=request_body,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
        }
    )
    
    start_time = time.time()
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
        
        content = result['choices'][0]['message']['content']
        elapsed = time.time() - start_time
        
        # 解析翻译结果
        translations = parse_translations(content, segments)
        
        # 写入输出文件
        output_data = {
            "batch_number": batch_num,
            "translations": translations
        }
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        return {
            'batch': batch_num,
            'success': True,
            'count': len(translations),
            'time': round(elapsed, 1),
            'file': os.path.basename(output_path)
        }
    
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            'batch': batch_num,
            'success': False,
            'error': str(e),
            'time': round(elapsed, 1)
        }


def parse_translations(content, segments):
    """解析 LLM 返回的翻译文本"""
    translations = []
    
    # 按 [ID: xxx] 分割
    import re
    parts = re.split(r'\[ID:\s*([^\]]+)\]', content)
    
    id_translation_map = {}
    for i in range(1, len(parts), 2):
        seg_id = parts[i].strip()
        translation = parts[i + 1].strip() if i + 1 < len(parts) else ""
        id_translation_map[seg_id] = translation
    
    # 按原始顺序组装
    for seg in segments:
        target = id_translation_map.get(seg['id'], "")
        translations.append({
            'id': seg['id'],
            'source': seg['source'],
            'target': target
        })
    
    return translations


def main():
    parser = argparse.ArgumentParser(description='DeepSeek API 直接翻译')
    parser.add_argument('batches_dir', help='批次文件目录')
    parser.add_argument('output_dir', help='输出目录')
    parser.add_argument('--workers', type=int, default=4, help='并行线程数（默认4）')
    parser.add_argument('--source-lang', default='zh-CN')
    parser.add_argument('--target-lang', default='en-US')
    parser.add_argument('--batches', nargs='*', help='指定批次号（如 7 8 9），不指定则翻译所有缺失的')
    
    args = parser.parse_args()
    
    # 找出需要翻译的批次
    batch_files = sorted([
        f for f in os.listdir(args.batches_dir)
        if f.startswith('batch_') and f.endswith('.json') and f != 'manifest.json'
    ])
    
    tasks = []
    for bf in batch_files:
        batch_num = int(bf.replace('batch_', '').replace('.json', ''))
        output_path = os.path.join(args.output_dir, bf)
        
        if args.batches and batch_num not in [int(b) for b in args.batches]:
            continue
        
        if not args.batches and os.path.exists(output_path):
            continue  # 跳过已完成的
        
        tasks.append({
            'batch_path': os.path.join(args.batches_dir, bf),
            'output_path': output_path,
            'batch_num': batch_num
        })
    
    if not tasks:
        print("没有需要翻译的批次")
        return
    
    total_start = time.time()
    print(f"开始翻译 {len(tasks)} 个批次，{args.workers} 个线程并行\n")
    
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for task in tasks:
            future = executor.submit(
                translate_batch,
                task['batch_path'],
                task['output_path'],
                args.source_lang,
                args.target_lang
            )
            futures[future] = task['batch_num']
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            if result['success']:
                print(f"  ✅ 批次 {result['batch']:2d}: {result['count']} 条翻译, {result['time']}秒")
            else:
                print(f"  ❌ 批次 {result['batch']:2d}: 失败 - {result['error']}")
    
    total_time = time.time() - total_start
    success = sum(1 for r in results if r['success'])
    total_segs = sum(r.get('count', 0) for r in results if r['success'])
    
    print(f"\n{'='*50}")
    print(f"完成: {success}/{len(tasks)} 批次成功")
    print(f"翻译: {total_segs} 段")
    print(f"总耗时: {total_time:.1f} 秒")
    print(f"平均: {total_time/len(tasks):.1f} 秒/批次")


if __name__ == '__main__':
    main()
