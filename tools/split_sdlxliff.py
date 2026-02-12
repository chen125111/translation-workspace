#!/usr/bin/env python3
"""
SDLXLIFF 拆分工具 — 将大型 SDLXLIFF 文件拆分成小批次用于翻译

用法:
  python3 split_sdlxliff.py <input.sdlxliff> <output_dir> [--batch-size 50]
"""

import xml.etree.ElementTree as ET
import json
import os
import sys
import argparse
import re


def extract_segments(sdlxliff_path, extract_all=False):
    """从 SDLXLIFF 文件中提取待翻译段落
    
    extract_all=True: 提取全部段落（忽略已有译文，全部重翻）
    extract_all=False: 只提取 target 为空的段落
    """
    tree = ET.parse(sdlxliff_path)
    root = tree.getroot()
    
    # SDLXLIFF 命名空间
    ns = {
        'xliff': 'urn:oasis:names:tc:xliff:document:1.2',
        'sdl': 'http://sdl.com/FileTypes/SdlXliff/1.0'
    }
    
    segments = []
    
    # 尝试多种提取方式
    # 方式1: 标准 XLIFF trans-unit
    for tu in root.iter('{urn:oasis:names:tc:xliff:document:1.2}trans-unit'):
        tu_id = tu.get('id', '')
        source_elem = tu.find('{urn:oasis:names:tc:xliff:document:1.2}source')
        target_elem = tu.find('{urn:oasis:names:tc:xliff:document:1.2}target')
        
        if source_elem is not None:
            source_text = ''.join(source_elem.itertext()).strip()
            target_text = ''
            if target_elem is not None:
                target_text = ''.join(target_elem.itertext()).strip()
            
            if source_text and (extract_all or not target_text):
                segments.append({
                    'id': tu_id,
                    'source': source_text
                })
    
    # 方式2: 如果上面没提取到，尝试不带命名空间
    if not segments:
        for tu in root.iter('trans-unit'):
            tu_id = tu.get('id', '')
            source_elem = tu.find('source')
            if source_elem is not None:
                source_text = ''.join(source_elem.itertext()).strip()
                if source_text:
                    segments.append({
                        'id': tu_id,
                        'source': source_text
                    })
    
    return segments


def split_into_batches(segments, batch_size=50):
    """将段落均匀拆分成批次
    
    不再简单按 batch_size 切割（会导致最后一批极少），
    而是先算出需要多少批，再把段落均匀分配到每批。
    例: 162段, batch_size=40 → 5批 → 33,33,32,32,32
    """
    total = len(segments)
    if total == 0:
        return []
    
    # 计算需要几批（向上取整）
    num_batches = max(1, -(-total // batch_size))  # ceil division
    
    # 均匀分配: 前 remainder 批多1个
    base_size = total // num_batches
    remainder = total % num_batches
    
    batches = []
    idx = 0
    for i in range(num_batches):
        size = base_size + (1 if i < remainder else 0)
        batches.append(segments[idx:idx + size])
        idx += size
    
    return batches


def save_batches(batches, output_dir, project_name="translation"):
    """保存批次文件"""
    os.makedirs(output_dir, exist_ok=True)
    
    manifest = {
        'project': project_name,
        'total_segments': sum(len(b) for b in batches),
        'total_batches': len(batches),
        'batch_files': []
    }
    
    for i, batch in enumerate(batches):
        filename = f"batch_{i+1:03d}.json"
        filepath = os.path.join(output_dir, filename)
        
        batch_data = {
            'batch_number': i + 1,
            'total_batches': len(batches),
            'segment_count': len(batch),
            'segments': batch
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, ensure_ascii=False, indent=2)
        
        manifest['batch_files'].append(filename)
        print(f"  批次 {i+1}/{len(batches)}: {len(batch)} 个段落 -> {filename}")
    
    # 保存清单
    manifest_path = os.path.join(output_dir, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    print(f"\n清单文件: {manifest_path}")
    return manifest


def main():
    parser = argparse.ArgumentParser(description='SDLXLIFF 拆分工具')
    parser.add_argument('input', help='输入 SDLXLIFF 文件路径')
    parser.add_argument('output_dir', help='输出目录')
    parser.add_argument('--batch-size', type=int, default=50, help='每批段落数（默认50）')
    parser.add_argument('--project', default='translation', help='项目名称')
    parser.add_argument('--all', action='store_true', help='提取全部段落（包括已有译文的，用于全部重翻）')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}", file=sys.stderr)
        sys.exit(1)
    
    mode = "全部段落" if args.all else "仅未翻译段落"
    print(f"正在提取: {args.input} ({mode})")
    segments = extract_segments(args.input, extract_all=args.all)
    
    if not segments:
        print("警告: 未提取到任何待翻译段落", file=sys.stderr)
        sys.exit(1)
    
    print(f"共提取 {len(segments)} 个待翻译段落")
    
    batches = split_into_batches(segments, args.batch_size)
    print(f"拆分为 {len(batches)} 个批次（每批最多 {args.batch_size} 段）\n")
    
    manifest = save_batches(batches, args.output_dir, args.project)
    
    print(f"\n✅ 完成！共 {manifest['total_segments']} 段，{manifest['total_batches']} 批")
    print(f"   输出目录: {args.output_dir}")


if __name__ == '__main__':
    main()
