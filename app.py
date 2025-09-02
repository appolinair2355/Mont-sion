from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import yaml, io, xlsxwriter, xlrd2, os, uuid, re
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ecole-mont-sion-clean')
PORT = int(os.environ.get('PORT', 10000))
DATABASE = 'database.yaml'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MATIERES = ['Mathématiques', 'Français', 'Anglais', 'Histoire', 'Géographie',
            'Sciences', 'SVT', 'Physique', 'Chimie']
TRIMESTRES = ['T1', 'T2', 'T3']

def load_data():
    try:
        with open(DATABASE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {'primaire': [], 'secondaire': []}
        for niv in ['primaire', 'secondaire']:
            for s in data.setdefault(niv, []):
                s.setdefault('notes', {m: {t: None for t in TRIMESTRES} for m in MATIERES})
                s.setdefault('paiements', [])
        return data
    except FileNotFoundError:
        return {'primaire': [], 'secondaire': []}

def save_data(data):
    with open(DATABASE, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = load_data()
        nom = request.form['nom'].strip().upper()
        prenoms = request.form['prenoms'].strip().title()
        classe = request.form['classe']
        sexe = request.form['sexe']
        date_naissance = request.form['date_naissance']
        parent = request.form['parent'].strip().title()
        phone = re.sub(r'\D', '', request.form['parent_phone'])
        frais = int(request.form['frais'])
        niveau = request.form['niveau']
        data.setdefault(niveau, []).append({
            'id': str(uuid.uuid4()),
            'nom': nom, 'prenoms': prenoms, 'classe': classe, 'sexe': sexe,
            'date_naissance': date_naissance, 'parent': parent, 'parent_phone': phone,
            'frais_total': frais, 'notes': {m: {t: None for t in TRIMESTRES} for m in MATIERES},
            'paiements': [], 'date_inscription': datetime.now().strftime('%d/%m/%Y')
        })
        save_data(data)
        flash('Élève inscrit', 'success')
        return redirect(url_for('students'))
    return render_template('register.html')

@app.route('/students')
def students():
    data = load_data()
    all_st = data['primaire'] + data['secondaire']
    classes = sorted({s.get('classe', 'Sans classe') for s in all_st})
    grouped = {c: [s for s in all_st if s.get('classe') == c] for c in classes}
    return render_template('students.html', grouped=grouped)

@app.route('/notes', methods=['GET', 'POST'])
def notes():
    data = load_data()
    students = data['primaire'] + data['secondaire']
    if request.method == 'POST':
        for s in students:
            for m in MATIERES:
                for t in TRIMESTRES:
                    val = request.form.get(f"{s['id']}_{m}_{t}", '').strip()
                    s['notes'][m][t] = float(val) if val else None
        save_data(data)
        flash('Notes sauvegardées', 'success')
        return redirect(url_for('notes'))
    return render_template('notes.html', students=students, matieres=MATIERES, trimestres=TRIMESTRES)

@app.route('/scolarite', methods=['GET', 'POST'])
def scolarite():
    data = load_data()
    students = data['primaire'] + data['secondaire']
    if request.method == 'POST':
        sid = request.form['student_id']
        amount = int(request.form['amount'])
        pwd = request.form.get('password')
        if pwd != 'kouame':
            flash('Mot de passe incorrect', 'error')
            return redirect(url_for('scolarite'))
        for niv in ['primaire', 'secondaire']:
            for s in data[niv]:
                if s['id'] == sid:
                    s['paiements'].append({'date': datetime.now().strftime('%d/%m/%Y'), 'montant': amount, 'mode': 'Espèces'})
                    save_data(data)
                    flash('Paiement enregistré', 'success')
                    return redirect(url_for('scolarite'))
    return render_template('scolarite.html', students=students)

@app.route('/export_excel')
def export_excel():
    data = load_data()
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {'in_memory': True})
    ws = wb.add_worksheet('Élèves')
    headers = ['Nom', 'Prénoms', 'Classe', 'Sexe', 'DateNaissance', 'Parent', 'Téléphone', 'FraisTotal']
    for m in MATIERES:
        for t in TRIMESTRES:
            headers.append(f'{m}{t}')
    max_p = max([len(s.get('paiements', [])) for s in data['primaire'] + data['secondaire']], default=0)
    for i in range(1, max_p + 1):
        headers.append(f'Paiement{i}')
    headers.append('Reste')
    for col, h in enumerate(headers):
        ws.write(0, col, h)
    row = 1
    for s in data['primaire'] + data['secondaire']:
        ws.write(row, 0, s['nom'])
        ws.write(row, 1, s['prenoms'])
        ws.write(row, 2, s['classe'])
        ws.write(row, 3, s['sexe'])
        ws.write(row, 4, s['date_naissance'])
        ws.write(row, 5, s['parent'])
        ws.write(row, 6, s['parent_phone'])
        ws.write(row, 7, s['frais_total'])
        col = 8
        for m in MATIERES:
            for t in TRIMESTRES:
                ws.write(row, col, s['notes'][m][t] or '')
                col += 1
        for p in s['paiements']:
            ws.write(row, col, p['montant'])
            col += 1
        reste = s['frais_total'] - sum(p['montant'] for p in s['paiements'])
        ws.write(row, col, reste)
        row += 1
    wb.close()
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue()),
                     as_attachment=True,
                     download_name=f"eleves_{datetime.now():%Y%m%d_%H%M%S}.xlsx")

# ------------- PAS DE HANDLERS 404/500 -------------
# Flask renvoie ses pages d’erreur par défaut si jamais besoin

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=False)
                
