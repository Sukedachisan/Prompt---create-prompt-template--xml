import os
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime

from jinja2 import Environment, FileSystemLoader, select_autoescape, TemplateError

class PromptTemplateGeneratorError(Exception):
    """プロンプトテンプレートジェネレータ用のカスタム例外クラス"""
    pass

class PromptTemplateGenerator:
    def __init__(self, template_dir: str = 'templates', output_dir: str = 'outputs'):
        """
        プロンプトテンプレートジェネレータの初期化
        
        Args:
            template_dir (str): テンプレートファイルが格納されるディレクトリ
            output_dir (str): 出力ファイルが保存されるディレクトリ
        """
        # ロギングの設定
        logging.basicConfig(
            level=logging.INFO, 
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)

        # ディレクトリの検証と作成
        self._validate_and_create_directories(template_dir, output_dir)
        
        # Jinja2環境の設定
        self.env = self._setup_jinja2_environment(template_dir)
        
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)

    def _extract_sub_items(self, element: ET.Element) -> List[Dict[str, Any]]:
        """
        要素からサブ項目を抽出する
        
        Args:
            element (ET.Element): XML要素
        
        Returns:
            List[Dict[str, Any]]: サブ項目のリスト
        """
        sub_items = []
        
        # メインテキストの処理
        main_text = element.text.strip() if element.text else None
        if main_text:
            sub_items.append({
                'text': main_text,
                'sub_items': []
            })
        
        # サブ項目の処理
        for sub_element in element.findall('*'):
            if sub_element.tag in ['description', 'note', 'example']:
                current_item = sub_items[-1] if sub_items else {'text': '', 'sub_items': []}
                
                sub_item = {
                    'type': sub_element.tag,
                    'text': sub_element.text.strip() if sub_element.text else ''
                }
                
                current_item['sub_items'].append(sub_item)
                
                if not sub_items:
                    sub_items.append(current_item)
        
        return sub_items

    def parse_xml_template(self, xml_file: Union[str, Path]) -> Dict[str, Any]:
        """
        XMLテンプレートファイルをパースし、テンプレート情報を抽出
        
        Args:
            xml_file (Union[str, Path]): パースするXMLファイルのパス
        
        Returns:
            Dict[str, Any]: テンプレート情報
        """
        try:
            xml_path = Path(xml_file)
            if not xml_path.exists():
                raise FileNotFoundError(f"テンプレートファイルが見つかりません: {xml_path}")
            
            tree = ET.parse(xml_path)
            root = tree.getroot()
            
            template_info: Dict[str, Any] = {
                'name': root.get('name', 'unnamed_template'),
                'description': root.findtext('description', ''),
                'sections': []
            }
            
            # セクションの抽出
            for section in root.findall('section'):
                section_info: Dict[str, Any] = {
                    'type': section.get('type', ''),
                    'content': section.text.strip() if section.text else ''
                }
                
                section_type = section.get('type')
                if section_type in ['languages', 'rules', 'requirements', 'libraries']:
                    section_info[section_type] = [
                        {
                            'text': item.text.strip() if item.text else '',
                            'sub_items': self._extract_sub_items(item)
                        } 
                        for item in section.findall(section_type[:-1])
                    ]
                
                template_info['sections'].append(section_info)
            
            return template_info
        
        except ET.ParseError as e:
            self.logger.error(f"XMLのパースエラー: {e}")
            raise

    def render_template(self, template_name: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        テンプレートをレンダリングし、プロンプトを生成
        
        Args:
            template_name (str): レンダリングするテンプレート名
            context (Optional[Dict[str, Any]], optional): テンプレートに渡すコンテキスト変数
        
        Returns:
            str: レンダリングされたプロンプト
        """
        try:
            context = context or {}
            template = self.env.get_template(template_name)
            return template.render(context)
        except TemplateError as e:
            self.logger.error(f"テンプレートレンダリングエラー: {e}")
            raise

    def _validate_and_create_directories(self, template_dir: str, output_dir: str) -> None:
        """
        テンプレートとアウトプットディレクトリの検証と作成
        
        Args:
            template_dir (str): テンプレートディレクトリ
            output_dir (str): 出力ディレクトリ
        
        Raises:
            PermissionError: ディレクトリ作成に必要な権限がない場合
        """
        try:
            Path(template_dir).mkdir(parents=True, exist_ok=True)
            Path(output_dir).mkdir(parents=True, exist_ok=True)
        except PermissionError as e:
            self.logger.error(f"ディレクトリ作成エラー: {e}")
            raise

    def _setup_jinja2_environment(self, template_dir: str) -> Environment:
        """
        Jinja2環境の設定
        
        Args:
            template_dir (str): テンプレートディレクトリ
        
        Returns:
            Environment: 設定されたJinja2環境
        """
        return Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['xml']),
            extensions=['jinja2.ext.do'],
            trim_blocks=True,
            lstrip_blocks=True
        )

    def save_prompt(self, prompt: str, prefix: str = 'prompt') -> Path:
        """
        生成されたプロンプトをテキストファイルに保存
        
        Args:
            prompt (str): 保存するプロンプト
            prefix (str, optional): ファイル名のプレフィックス
        
        Returns:
            Path: 保存されたファイルのパス
        
        Raises:
            IOError: ファイル保存に失敗した場合
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{prefix}_{timestamp}.txt"
            filepath = self.output_dir / filename
            
            with filepath.open('w', encoding='utf-8') as f:
                f.write(prompt)
            
            self.logger.info(f"プロンプトを {filepath} に保存しました。")
            return filepath
        except IOError as e:
            self.logger.error(f"ファイル保存エラー: {e}")
            raise

    def generate_prompt_template(
        self, 
        template_name: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        プロンプトテンプレートの生成と保存を一括で行う
        
        Args:
            template_name (str): 使用するテンプレート名
            context (Optional[Dict[str, Any]], optional): テンプレートコンテキスト
        
        Returns:
            Path: 生成・保存されたプロンプトファイルのパス
        """
        try:
            # テンプレート情報の取得
            self.parse_xml_template(self.template_dir / template_name)
            
            # テンプレートのレンダリング
            rendered_prompt = self.render_template(template_name, context)
            
            # プロンプトの保存
            return self.save_prompt(rendered_prompt, prefix='claude_prompt')
        
        except Exception as e:
            self.logger.error(f"プロンプトテンプレート生成エラー: {e}")
            raise PromptTemplateGeneratorError(f"プロンプトテンプレートの生成に失敗しました: {e}")

def main():
    generator = PromptTemplateGenerator()
    
    # テンプレート情報の確認
    template_info = generator.parse_xml_template('templates/comprehensive_task_template.xml')
    print(template_info)

if __name__ == '__main__':
    main()

# サンプルXMLテンプレート (templates/comprehensive_task_template.xml)
"""
<?xml version="1.0" encoding="UTF-8"?>
<prompt name="comprehensive_code_generation_template">
    <description>包括的な高度なタスク用のプロンプトテンプレート</description>
    <section type="system">
        あなたは高度な{{ task_type }}AIです。
    </section>
    <section type="user">
        {% if complexity == 'advanced' %}
        非常に複雑で詳細な実装が求められるタスクを処理してください。

        <section type="languages">
            <language>
                Python 12
                <description>最新の言語機能を活用</description>
                <example>型ヒント、非同期プログラミングなど</example>
            </language>
            <language>
                Type Hints
                <note>静的型付けを徹底的に活用</note>
            </language>
        </section>

        <section type="libraries">
            <library>
                Jinja2
                <description>高度なテンプレート生成ライブラリ</description>
                <example>動的なコード生成に最適</example>
            </library>
            <library>
                NumPy
                <note>科学計算と数値計算のための高速ライブラリ</note>
            </library>
        </section>

        <section type="rules">
            <rule>
                コードの可読性と保守性を最優先にすること
                <description>読みやすく、理解しやすいコードを心がける</description>
                <example>適切な命名、コメント、型ヒントの使用</example>
            </rule>
            <rule>
                最新のベストプラクティスに従うこと
                <note>継続的な学習と改善が重要</note>
            </rule>
        </section>

        <section type="requirements">
            <requirement>
                完全で詳細な実装を提供すること
                <description>すべての機能要件を満たす実装</description>
                <example>エッジケースの考慮、テストカバレッジ</example>
            </requirement>
            <requirement>
                エラーハンドリングを comprehensive に行うこと
                <note>すべての潜在的なエラーケースに対応</note>
            </requirement>
        </section>
        {% else %}
        基本的なタスクを処理してください。
        {% endif %}
    </section>
</prompt>
"""

# テンプレート用のJinja2テンプレート (templates/prompt_template.j2)
"""
# 使用するプログラミング言語
{% for language in languages %}
- {{ language.text }}
  {% for sub_item in language.sub_items %}
    {% if sub_item.type == 'description' %}
    説明: {{ sub_item.text }}
    {% elif sub_item.type == 'note' %}
    補足: {{ sub_item.text }}
    {% elif sub_item.type == 'example' %}
    例: {{ sub_item.text }}
    {% endif %}
  {% endfor %}
{% endfor %}

# 主要ライブラリ
{% for library in libraries %}
- {{ library.text }}
  {% for sub_item in library.sub_items %}
    {% if sub_item.type == 'description' %}
    説明: {{ sub_item.text }}
    {% elif sub_item.type == 'note' %}
    補足: {{ sub_item.text }}
    {% elif sub_item.type == 'example' %}
    例: {{ sub_item.text }}
    {% endif %}
  {% endfor %}
{% endfor %}

# ルール
{% for rule in rules %}
- {{ rule.text }}
  {% for sub_item in rule.sub_items %}
    {% if sub_item.type == 'description' %}
    説明: {{ sub_item.text }}
    {% elif sub_item.type == 'note' %}
    補足: {{ sub_item.text }}
    {% elif sub_item.type == 'example' %}
    例: {{ sub_item.text }}
    {% endif %}
  {% endfor %}
{% endfor %}

# 要件
{% for requirement in requirements %}
- {{ requirement.text }}
  {% for sub_item in requirement.sub_items %}
    {% if sub_item.type == 'description' %}
    説明: {{ sub_item.text }}
    {% elif sub_item.type == 'note' %}
    補足: {{ sub_item.text }}
    {% elif sub_item.type == 'example' %}
    例: {{ sub_item.text }}
    {% endif %}
  {% endfor %}
{% endfor %}
""
















    
    

    



def main():
    try:
        # 使用例
        generator = PromptTemplateGenerator()
        
        # コンテキストの設定
        context = {
            'task_type': 'code_generation',
            'complexity': 'advanced',
            'languages': ['Python 12', 'Type Hints'],
            'libraries': ['Jinja2', 'NumPy'],
            'rules': [
                'コードの可読性と保守性を最優先にすること',
                '最新のベストプラクティスに従うこと'
            ],
            'requirements': [
                '完全で詳細な実装を提供すること',
                'エラーハンドリングを comprehensive に行うこと'
            ]
        }
        
        # プロンプトテンプレートの生成
        output_file = generator.generate_prompt_template('advanced_task_template.xml', context)
        print(f"プロンプトテンプレートを {output_file} に生成しました。")
    
    except PromptTemplateGeneratorError as e:
        print(f"エラーが発生しました: {e}")

if __name__ == '__main__':
    main()
