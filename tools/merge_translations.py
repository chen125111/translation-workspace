#!/usr/bin/env python3
"""
翻译合并工具 — 将翻译好的批次结果合并回原 SDLXLIFF 文件

用法:
  python3 merge_translations.py <original.sdlxliff> <output_dir> <merged_output.sdlxliff>
"""

import xml.etree.ElementTree as ET
import json
import os
import sys
import argparse
import glob


def load_all_translations(output_dir):
    """加载所有翻译结果"""
    translations = {}
    
    pattern = os.path.join(output_dir, 'batch_*.json')
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if 'translations' in data:
            for item in data['translations']:
                if 'id' in item and 'target' in item:
                    translations[item['id']] = item['target']
    
    return translations


def merge_into_sdlxliff(sdlxliff_path, translations, output_path):
    """将翻译结果写回 SDLXLIFF 文件"""
    tree = ET.parse(sdlxliff_path)
    root = tree.getroot()
    
    merged_count = 0
    missing_count = 0
    
    for tu in root.iter('{urn:oasis:names:tc:xliff:document:1.2}trans-unit'):
        tu_id = tu.get('id', '')
        
        if tu_id in translations:
            target_elem = tu.find('{urn:oasis:names:tc:xliff:document:1.2}target')
            
            if target_elem is None:
                target_elem = ET.SubElement(tu, '{urn:oasis:names:tc:xliff:document:1.2}target')
            
            target_elem.text = translations[tu_id]
            merged_count += 1
        else:
            source_elem = tu.find('{urn:oasis:names:tc:xliff:document:1.2}source')
            if source_elem is not None:
                source_text = ''.join(source_elem.itertext()).strip()
                if source_text:
                    missing_count += 1
    
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
    
    return merged_count, missing_count


def main():
    parser = argparse.ArgumentParser(description='翻译合并工具')
    parser.add_argument('original', help='原始 SDLXLIFF 文件')
    parser.add_argument('translations_dir', help='翻译结果目录（含 batch_*.json）')
    parser.add_argument('output', help='输出合并后的 SDLXLIFF 文件')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.original):
        print(f"错误: 原始文件不存在: {args.original}", file=sys.stderr)
        sys.exit(1)
    
    print(f"加载翻译结果: {args.translations_dir}")
    translations = load_all_translations(args.translations_dir)
    print(f"共加载 {len(translations)} 条翻译")
    
    print(f"合并到: {args.output}")
    merged, missing = merge_into_sdlxliff(args.original, translations, args.output)
    
    print(f"\n✅ 合并完成")
    print(f"   已合并: {merged} 条")
    print(f"   缺失翻译: {missing} 条")
    print(f"   输出文件: {args.output}")


if __name__ == '__main__':
    main()
