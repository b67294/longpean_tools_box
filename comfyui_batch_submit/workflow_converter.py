"""
ComfyUI 工作流格式转换工具
将 ComfyUI 导出的工作流 JSON 转换为 API Prompt 格式
"""

import json
from pathlib import Path
from typing import Dict, Any


def convert_workflow_to_prompt(workflow_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 ComfyUI 工作流 JSON 转换为 API Prompt 格式
    
    Args:
        workflow_json: ComfyUI 导出的工作流 JSON
    
    Returns:
        转换后的 API Prompt 格式 JSON
    """
    prompt = {}
    
    # 检查是否已经是 prompt 格式
    if "nodes" not in workflow_json:
        # 可能已经是 prompt 格式
        return {"prompt": workflow_json}
    
    # 遍历 nodes，转换为 prompt 格式
    for node in workflow_json.get("nodes", []):
        node_id = str(node.get("id"))
        
        # 跳过不需要执行的节点类型
        if node.get("type") in ["Note", "Reroute"]:
            continue
        
        node_data = {
            "class_type": node.get("type"),
            "inputs": {}
        }
        
        # 处理输入
        if "inputs" in node:
            for input_item in node["inputs"]:
                input_name = input_item.get("name")
                
                # 如果有链接，使用链接引用；否则使用 widget 值
                if input_item.get("link") is not None:
                    # 这里暂时跳过链接处理，因为需要根据 links 来完成
                    pass
                elif "widget" in input_item:
                    widget_name = input_item["widget"].get("name")
                    if widget_name:
                        # 从 widgets_values 获取值
                        if "widgets_values" in node:
                            widget_index = 0
                            # 找到对应的 widget 在 widgets_values 中的索引
                            widget_counter = 0
                            for inp in node["inputs"]:
                                if "widget" in inp:
                                    if inp["widget"].get("name") == widget_name:
                                        break
                                    widget_counter += 1
                            
                            if widget_counter < len(node.get("widgets_values", [])):
                                node_data["inputs"][input_name] = node["widgets_values"][widget_counter]
        
        prompt[node_id] = node_data
    
    # 处理链接关系
    for link in workflow_json.get("links", []):
        link_id, source_node_id, source_output, target_node_id, target_input_idx, type_str = link
        
        source_id = str(source_node_id)
        target_id = str(target_node_id)
        
        if source_id in prompt and target_id in prompt:
            # 找到目标节点的目标输入名称
            target_node = None
            for node in workflow_json.get("nodes", []):
                if str(node.get("id")) == target_id:
                    target_node = node
                    break
            
            if target_node and "inputs" in target_node:
                if target_input_idx < len(target_node["inputs"]):
                    input_name = target_node["inputs"][target_input_idx].get("name")
                    # 设置链接关系 [source_node_id, source_output_index]
                    prompt[target_id]["inputs"][input_name] = [int(source_id), int(source_output)]
    
    return {"prompt": prompt}


def process_json_file(json_path: Path) -> bool:
    """
    处理单个 JSON 文件，转换后保存
    
    Args:
        json_path: JSON 文件路径
    
    Returns:
        是否成功转换
    """
    try:
        # 读取原始文件
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 检查是否需要转换
        if "nodes" in data:
            # 这是工作流格式，需要转换
            prompt = convert_workflow_to_prompt(data)
            save_path = json_path.parent / f"{json_path.stem}_api.json"
        else:
            # 已经是 API 格式
            prompt = data
            save_path = json_path
        
        # 保存转换后的文件
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(prompt, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 转换成功: {json_path.name} -> {save_path.name}")
        return True
    
    except Exception as e:
        print(f"✗ 转换失败: {json_path.name} - {e}")
        return False


def main():
    """主函数"""
    json_folder = Path(__file__).parent / "json_files"
    
    if not json_folder.exists():
        print(f"错误：文件夹不存在 {json_folder}")
        return
    
    json_files = list(json_folder.glob("*.json"))
    
    if not json_files:
        print("未找到任何 JSON 文件")
        return
    
    print(f"找到 {len(json_files)} 个 JSON 文件")
    print("-" * 50)
    
    successful = 0
    failed = 0
    
    for json_file in json_files:
        # 跳过已转换的文件
        if "_api" in json_file.name:
            continue
        
        if process_json_file(json_file):
            successful += 1
        else:
            failed += 1
    
    print("-" * 50)
    print(f"转换完成！成功: {successful}, 失败: {failed}")


if __name__ == "__main__":
    main()
