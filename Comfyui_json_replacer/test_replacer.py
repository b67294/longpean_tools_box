#!/usr/bin/env python3
"""
ComfyUI JSON 替换工具 - 快速测试脚本
"""
import json
from pathlib import Path


def test_json_replacer():
    """测试 JSON 替换功能"""
    
    # 创建测试用的样本 JSON
    sample_workflow = {
        "1": {
            "inputs": {
                "ckpt_name": "model.safetensors"
            },
            "class_type": "CheckpointLoaderSimple",
            "_meta": {"title": "Load Checkpoint"}
        },
        "2": {
            "inputs": {
                "text": "original prompt text",
                "clip": ["1", 1]
            },
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "CLIP Text Encode"}
        },
        "8": {
            "inputs": {
                "seed": 0,
                "steps": 20,
                "cfg": 8.0,
                "sampler_name": "euler",
                "scheduler": "normal"
            },
            "class_type": "KSampler",
            "_meta": {"title": "KSampler"}
        },
        "15": {
            "inputs": {
                "url": "https://example.com/image.jpg",
                "download": True
            },
            "class_type": "LoadImageFromUrl",
            "_meta": {"title": "Load Image from URL"}
        }
    }
    
    # 测试替换规则
    test_rules = [
        ("2", "text", "新的提示词内容"),
        ("8", "seed", "123456"),
        ("15", "url", "#{image}"),
        ("1", "ckpt_name", "new_model.safetensors"),
    ]
    
    print("=" * 80)
    print("ComfyUI JSON 替换工具 - 测试")
    print("=" * 80)
    print(f"\n原始 JSON 数据（{len(sample_workflow)} 个节点）:")
    print(json.dumps(sample_workflow, indent=2, ensure_ascii=False))
    
    print(f"\n\n【替换规则】({len(test_rules)} 条):")
    for node_id, field, new_value in test_rules:
        print(f"  节点 {node_id} → {field} = {new_value}")
    
    print("\n\n【执行替换】:")
    print("-" * 80)
    
    replaced_count = 0
    for node_id, field, new_value in test_rules:
        if node_id in sample_workflow:
            node = sample_workflow[node_id]
            if "inputs" in node and field in node["inputs"]:
                old_value = node["inputs"][field]
                node["inputs"][field] = new_value
                node_name = node.get("class_type", "Unknown")
                
                print(f"[成功] 节点 {node_id} ({node_name})")
                print(f"  字段: {field}")
                print(f"  替换前: {old_value}")
                print(f"  替换后: {new_value}")
                print("-" * 80)
                replaced_count += 1
            else:
                print(f"[失败] 节点 {node_id} 不存在字段 '{field}'")
        else:
            print(f"[失败] 节点 {node_id} 不存在")
    
    print("\n\n【替换后的 JSON】:")
    print(json.dumps(sample_workflow, indent=2, ensure_ascii=False))
    
    print(f"\n\n【总结】")
    print(f"总规则数: {len(test_rules)}")
    print(f"替换成功: {replaced_count}")
    print(f"替换失败: {len(test_rules) - replaced_count}")
    
    print("\n" + "=" * 80)
    print("✓ 测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    test_json_replacer()
