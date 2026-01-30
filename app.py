#!/usr/bin/env python3
"""
History Source Analyzer - Flask API
מערכת מלאה לניתוח מקורות היסטוריים
"""

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import anthropic

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config['CORS_HEADERS'] = 'Content-Type'
# הגדרות
STUDY_MATERIALS_DIR = Path(__file__).parent / 'study_materials'
API_KEY = os.environ.get('ANTHROPIC_API_KEY')

if not API_KEY:
    print("⚠️  אזהרה: חסר ANTHROPIC_API_KEY")


class HistoryAnalyzer:
    """מנתח מקורות היסטוריים"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = anthropic.Anthropic(api_key=api_key)
    
    def extract_text_from_docx(self, docx_path: str) -> str:
        """מחלץ טקסט מקובץ Word"""
        try:
            result = subprocess.run(
                ['pandoc', docx_path, '-t', 'plain', '--wrap=none'],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            raise Exception(f"שגיאה בחילוץ טקסט: {e}")
        except FileNotFoundError:
            raise Exception("pandoc לא מותקן")
    
    def call_claude_api(self, source: str, question: str, study_material: str) -> Dict[str, Any]:
        """קורא ל-Claude API"""
        
        prompt = f"""אתה מומחה להוראת היסטוריה בישראל. תפקידך לנתח מקור היסטורי ולעזור לתלמיד לענות על שאלת בחינה.

**קטע המקור:**
{source}

**השאלה:**
{question}

**חומר לימודי רלוונטי:**
{study_material[:15000]}

---

בצע ניתוח מלא של המקור ומענה לשאלה לפי המבנה הבא:

1. **זיהוי דרישות השאלה**:
   - מה בדיוק השאלה מבקשת?
   - אילו מיומנויות נדרשות? (הצג/הסבר/השווה/הדגם)
   - כמה פריטים נדרשים?

2. **ניתוח המקור**:
   - מאפייני המקור (סוג, יוצר, מטרה, מועד, קרבה לאירועים)
   - תוכן ומסרים מרכזיים
   - הקשר היסטורי

3. **חיבור לחומר הלימודי**:
   - אילו חלקים מהחומר רלוונטיים לשאלה?
   - איך החומר מסביר את המקור?

4. **בניית תשובה מושלמת**:
כתוב תשובה מדגם שעונה על השאלה לפי הכללים:
- משפט פתיחה קצר שמגדיר את המטלה
- עיגון במקור (ציטוט קצר או התייחסות לתוכן)
- שימוש בשפה משלך (לא העתקה)
- הסבר מלא (גורמים ותוצאות אם נדרש)
- שימוש בחומר הלימודי כשהשאלה מבקשת "על פי מה שלמדת"

5. **הערות להדרכת התלמיד**:
- על מה לשים לב?
- טעויות נפוצות
- טיפים להצלחה

**החזר בפורמט JSON:**

```json
{{
  "questionAnalysis": {{
    "requirements": "...",
    "skills": "...",
    "itemCount": "..."
  }},
  "sourceAnalysis": {{
    "characteristics": {{
      "type": "...",
      "author": "...",
      "purpose": "...",
      "datePlace": "...",
      "proximity": "..."
    }},
    "content": "...",
    "historicalContext": "..."
  }},
  "studyMaterialConnection": {{
    "relevantSections": "...",
    "explanation": "..."
  }},
  "modelAnswer": "...",
  "guidanceNotes": {{
    "keyPoints": "...",
    "commonMistakes": "...",
    "tips": "..."
  }}
}}
```

חשוב: כתוב הכל בעברית, בצורה ברורה ומקצועית."""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = ""
            for block in message.content:
                if hasattr(block, 'text'):
                    response_text += block.text
            
            # חילוץ JSON
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise Exception("לא נמצא JSON בתשובה")
            
            return json.loads(json_str)
            
        except Exception as e:
            raise Exception(f"שגיאה בקריאה ל-API: {str(e)}")
    
    def analyze(self, source: str, question: str, material_name: str) -> Dict[str, Any]:
        """ניתוח מלא"""
        # מציאת קובץ החומר
        docx_path = STUDY_MATERIALS_DIR / f"{material_name}.docx"
        
        if not docx_path.exists():
            raise Exception(f"קובץ החומר {material_name}.docx לא נמצא")
        
        # חילוץ החומר
        study_material = self.extract_text_from_docx(str(docx_path))
        
        # ניתוח
        analysis = self.call_claude_api(source, question, study_material)
        
        return analysis


# Routes

('/')
def index():
    """עמוד ראשי"""
    return """
    <h1>History Analyzer API</h1>
    <p>API is running!</p>
    <p>POST to /api/analyze to analyze a source</p>
    """

@app.route('/api/materials', methods=['GET'])
def list_materials():
    """רשימת חומרי לימוד זמינים"""
    materials = []
    if STUDY_MATERIALS_DIR.exists():
        materials = [f.stem for f in STUDY_MATERIALS_DIR.glob('*.docx')]
    
    return jsonify({
        'success': True,
        'materials': materials
    })
@app.route('/api/analyze', methods=['OPTIONS'])
def analyze_options():
    response = jsonify({'status': 'ok'})
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
    response.headers.add('Access-Control-Allow-Methods', 'POST')
    return response
@app.route('/api/analyze', methods=['POST'])
def analyze():
    """ניתוח מקור"""
    
    if not API_KEY:
        return jsonify({
            'success': False,
            'error': 'חסר API Key. יש להגדיר ANTHROPIC_API_KEY'
        }), 500
    
    try:
        data = request.json
        
        # וולידציה
        required_fields = ['source', 'question', 'material']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'חסר שדה: {field}'
                }), 400
        
        # ניתוח
        analyzer = HistoryAnalyzer(API_KEY)
        result = analyzer.analyze(
            source=data['source'],
            question=data['question'],
            material_name=data['material']
        )
        
        response = jsonify({'success': True, 'analysis': result})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """בדיקת תקינות"""
    return jsonify({
        'status': 'ok',
        'api_key_configured': bool(API_KEY),
        'study_materials_dir_exists': STUDY_MATERIALS_DIR.exists()
    })


if __name__ == '__main__':
    print("🚀 Starting History Analyzer API...")
    print(f"📚 Study materials directory: {STUDY_MATERIALS_DIR}")
    print(f"🔑 API Key configured: {bool(API_KEY)}")
    
    # הרצה
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
