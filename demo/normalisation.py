"""Normalisation des compétences (identique au notebook 07)."""
import re

NORMALISATION = {
    # langages et frameworks
    'js': 'JavaScript', 'javascript': 'JavaScript', 'es6': 'JavaScript', 'جافا سكريبت': 'JavaScript',
    'ts': 'TypeScript', 'typescript': 'TypeScript',
    'python3': 'Python', 'python': 'Python', 'بايثون': 'Python',
    'react.js': 'React', 'reactjs': 'React', 'react js': 'React',
    'vue': 'Vue.js', 'vuejs': 'Vue.js', 'vue 3': 'Vue.js', 'vue3': 'Vue.js',
    'nuxt.js': 'Nuxt', 'nuxtjs': 'Nuxt',
    'node': 'Node.js', 'nodejs': 'Node.js', 'node js': 'Node.js',
    'nest': 'NestJS', 'nest.js': 'NestJS', 'nestjs': 'NestJS',
    'next': 'Next.js', 'nextjs': 'Next.js',
    'express': 'Express.js', 'expressjs': 'Express.js',
    'angularjs': 'Angular', 'angular js': 'Angular',
    'spring': 'Spring', 'springboot': 'Spring Boot',
    'laravel 12': 'Laravel', 'laravel 11': 'Laravel',
    'java 17': 'Java', 'java 21': 'Java', 'java ee': 'JEE',
    'dotnet': '.NET', '.net core': '.NET', 'asp.net core': 'ASP.NET Core',
    'html': 'HTML', 'html5': 'HTML', 'css': 'CSS', 'css3': 'CSS',
    'tailwind': 'Tailwind CSS', 'tailwindcss': 'Tailwind CSS',
    # données
    'postgres': 'PostgreSQL', 'postgresql': 'PostgreSQL', 'postgre': 'PostgreSQL',
    'mongo': 'MongoDB', 'mongodb': 'MongoDB',
    'microsoft sql server': 'SQL Server', 'mssql': 'SQL Server', 'ms sql': 'SQL Server',
    'prisma orm': 'Prisma', 'typeorm orm': 'TypeORM', 'eloquent orm': 'Eloquent',
    'vector databases': 'bases vectorielles', 'vector database': 'bases vectorielles', 'moteurs vectoriels': 'bases vectorielles',
    'modélisation de données': 'data modeling', 'data modelling': 'data modeling', 'database design': 'data modeling',
    'data warehousing': 'data warehouse',
    # cloud / devops
    'microsoft azure': 'Azure', 'azure cloud': 'Azure', 'google cloud platform': 'GCP', 'google cloud': 'GCP',
    'amazon web services': 'AWS', 'lambda': 'AWS Lambda', 'aws lambda': 'AWS Lambda',
    'azuredevops': 'Azure DevOps', 'k8s': 'Kubernetes', 'kubernetes (eks)': 'Kubernetes',
    'github action': 'GitHub Actions', 'gitlab-ci': 'GitLab CI', 'gitlab ci/cd': 'GitLab CI',
    'elk': 'ELK Stack', 'elk stack': 'ELK Stack', 'micro-services': 'microservices', 'microservice': 'microservices',
    'continuous integration': 'intégration continue',
    # API
    'rest api': 'API REST', 'rest apis': 'API REST', 'restful api': 'API REST', 'restful apis': 'API REST',
    'restful services': 'API REST', 'apis rest': 'API REST', 'api restful': 'API REST', 'web apis': 'API REST',
    'webhook': 'webhooks',
    # IA
    'ia': 'intelligence artificielle', 'ai': 'intelligence artificielle', 'artificial intelligence': 'intelligence artificielle',
    'الذكاء الاصطناعي': 'intelligence artificielle',
    'ia générative': 'intelligence artificielle générative', 'generative ai': 'intelligence artificielle générative',
    'ia agentique': 'intelligence artificielle agentique', 'agentic ai': 'intelligence artificielle agentique',
    'ai agents': 'intelligence artificielle agentique',
    'ml': 'Machine Learning', 'apprentissage automatique': 'Machine Learning', 'machine learning': 'Machine Learning',
    'deep learning': 'Deep Learning', 'apprentissage profond': 'Deep Learning',
    'traitement automatique du langage naturel': 'NLP', 'large language models': 'LLM', 'llms': 'LLM',
    # méthodes et domaines
    'oop': 'programmation orientée objet', 'poo': 'programmation orientée objet',
    'rgpd': 'GDPR', 'software testing methodologies': 'Software Testing',
    'information security': "sécurité de l'information", 'أمن المعلومات': "sécurité de l'information",
    'cybersecurity': 'cybersécurité', 'cyber security': 'cybersécurité',
    'responsive': 'responsive design', 'التصميم المتجاوب': 'responsive design',
    'ui/ux': 'UI design', 'ux/ui': 'UI design',
    'تطوير البرمجيات': 'développement logiciel', 'software development': 'développement logiciel',
    'برمجة مواقع': 'développement web', 'تطوير الويب': 'développement web', 'web development': 'développement web',
    'هندسة البرمجيات': 'génie logiciel', 'software engineering': 'génie logiciel',
    'برمجة أندرويد': 'Android', 'برمجة ios': 'iOS', 'mobile development': 'développement mobile',
    'firewall': 'pare-feu', 'firewalls': 'pare-feu',
}
GARDER_SLASH = {'ci/cd', 'tcp/ip', 'pl/sql', 'pub/sub', 'tests a/b'}

def cle(s):
    s = re.sub(r'\s+', ' ', str(s).strip().lower())
    return s.strip(' ;,').rstrip('.')

def canon(competence):
    """Une compétence brute -> liste de noms canoniques (séparation des composés)."""
    k = cle(competence)
    if not k:
        return []
    morceaux = [k] if k in GARDER_SLASH or k in NORMALISATION else [m.strip() for m in k.split('/') if m.strip()]
    sortie = []
    for m in morceaux:
        m = re.sub(r'\s*\((.*?)\)\s*', ' ', m).strip() if m not in NORMALISATION else m
        sortie.append(NORMALISATION.get(m, m))
    return sortie

def ensemble(competences):
    """Liste brute -> ensemble de clés canoniques (minuscules)."""
    return {cle(c) for x in (competences or []) if isinstance(x, str) for c in canon(x)}
