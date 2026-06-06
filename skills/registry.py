import inspect
import functools
from typing import Callable, Dict, Any, List

class SkillRegistry:
    def __init__(self):
        self.skills: Dict[str, Dict[str, Any]] = {}

    def register(self, name: str = None, category: str = "general"):
        """
        裝飾器：將一個 Python 函式註冊為 Agent 技能。
        會自動解析函式的型態註解與 Docstring 來產生 LLM 兼容的 Tool Schema。
        """
        def decorator(func: Callable):
            nonlocal name
            skill_name = name or func.__name__
            
            # 解析 Docstring 做為描述
            doc = func.__doc__ or "無描述"
            description = doc.strip().split("\n")[0] # 第一行作為主描述
            
            # 解析參數
            sig = inspect.signature(func)
            properties = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name == "self":
                    continue
                
                # 判斷型態
                param_type = "STRING" # 預設型態
                if param.annotation == int:
                    param_type = "INTEGER"
                elif param.annotation == float:
                    param_type = "NUMBER"
                elif param.annotation == bool:
                    param_type = "BOOLEAN"
                elif param.annotation == list:
                    param_type = "ARRAY"
                
                # 參數描述 (這裡做簡化，可從 Docstring 解析，或預設)
                properties[param_name] = {
                    "type": param_type,
                    "description": f"參數 {param_name}"
                }
                
                # 如果沒有預設值，則是必填參數
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
                    
            # 建立 Gemini / OpenAI 兼容的 Tool Schema
            schema = {
                "name": skill_name,
                "description": description,
                "parameters": {
                    "type": "OBJECT",
                    "properties": properties,
                    "required": required
                }
            }
            
            self.skills[skill_name] = {
                "name": skill_name,
                "func": func,
                "schema": schema,
                "category": category,
                "enabled": True, # 預設啟用
                "doc": doc
            }
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
            
        return decorator

    def get_all_skills(self) -> List[Dict[str, Any]]:
        """獲取所有註冊的技能"""
        return list(self.skills.values())

    def get_enabled_skills(self) -> List[Dict[str, Any]]:
        """獲取當前啟用的技能"""
        return [s for s in self.skills.values() if s["enabled"]]

    def get_gemini_tools(self) -> List[Dict[str, Any]]:
        """獲取適合傳入 Google Gemini API 的工具格式"""
        # Gemini API 的 Function Declaration 可以直接包裝成工具
        # 我們將 schema 的 properties 和 required 傳出
        tools = []
        for skill in self.get_enabled_skills():
            tools.append(skill["schema"])
        return tools

    def execute(self, skill_name: str, **kwargs) -> Any:
        """執行指定的技能"""
        # 處理常見別名映射，增加對 LLM 工具呼叫的容錯性
        if skill_name not in self.skills:
            if skill_name == "search" and "web_search" in self.skills:
                skill_name = "web_search"
            elif skill_name == "read" and "read_file" in self.skills:
                skill_name = "read_file"
            elif skill_name == "write" and "write_file" in self.skills:
                skill_name = "write_file"
            elif skill_name == "list" and "list_dir" in self.skills:
                skill_name = "list_dir"
            elif skill_name == "fetch" and "fetch_webpage" in self.skills:
                skill_name = "fetch_webpage"

        if skill_name not in self.skills:
            raise ValueError(f"找不到技能: {skill_name}")
            
        skill = self.skills[skill_name]
        if not skill["enabled"]:
            raise PermissionError(f"技能 '{skill_name}' 目前已被停用。")
            
        func = skill["func"]
        
        # 進行參數型態轉換確保安全
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(**kwargs)
        
        # 執行並返回結果
        try:
            return func(**bound_args.arguments)
        except Exception as e:
            return f"執行錯誤: {str(e)}"

# 全域單例註冊中心
registry = SkillRegistry()

def skill(name: str = None, category: str = "general"):
    return registry.register(name, category)
