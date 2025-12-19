#!/usr/bin/env python3
"""
Exemples d'intégration API Kidjamo pour développeurs
Montre comment utiliser l'API pour récupérer et afficher les données d'activité
"""

import requests
import json
import asyncio
import websockets
from datetime import datetime
from typing import Dict, Any

class KidjamoAPIClient:
    """Client Python pour l'API Kidjamo"""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })

    def get_current_activity(self, device_id: str) -> Dict[str, Any]:
        """Récupère l'activité actuelle d'un device"""
        url = f"{self.base_url}/api/v1/activity/current/{device_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_activity_history(self, device_id: str, hours: int = 24) -> list:
        """Récupère l'historique d'activité"""
        url = f"{self.base_url}/api/v1/activity/history/{device_id}"
        params = {'hours': hours}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_activity_summary(self, patient_id: str, period: str = "24h") -> Dict[str, Any]:
        """Récupère le résumé d'activité"""
        url = f"{self.base_url}/api/v1/analytics/activity-summary/{patient_id}"
        params = {'period': period}
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def get_mobile_dashboard(self, patient_id: str) -> Dict[str, Any]:
        """Récupère le dashboard mobile optimisé"""
        url = f"{self.base_url}/api/v1/mobile/dashboard/{patient_id}"
        response = self.session.get(url)
        response.raise_for_status()
        return response.json()

    def get_alerts(self, patient_id: str, acknowledged: bool = None) -> list:
        """Récupère les alertes d'un patient"""
        url = f"{self.base_url}/api/v1/alerts/{patient_id}"
        params = {}
        if acknowledged is not None:
            params['acknowledged'] = acknowledged
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        """Acquitte une alerte"""
        url = f"{self.base_url}/api/v1/alerts/acknowledge"
        data = {'alert_id': alert_id}
        response = self.session.post(url, params=data)
        response.raise_for_status()
        return response.json()

# === EXEMPLES POUR APPLICATION MOBILE ===

def exemple_app_mobile():
    """Exemple d'intégration pour application mobile (React Native, Flutter, etc.)"""

    print("📱 EXEMPLE APPLICATION MOBILE")
    print("=" * 50)

    client = KidjamoAPIClient()
    patient_id = "patient_demo_001"

    try:
        # 1. Récupérer le dashboard mobile complet
        dashboard = client.get_mobile_dashboard(patient_id)

        print("🏠 Dashboard Mobile:")
        print(f"   Patient: {dashboard['patient_info']['name']}")
        print(f"   Activité: {dashboard['current_activity']['emoji']} {dashboard['current_activity']['title']}")
        print(f"   Magnitude: {dashboard['current_activity']['value']}")
        print(f"   Description: {dashboard['current_activity']['subtitle']}")

        # 2. Statistiques quotidiennes
        daily_stats = dashboard['daily_stats']
        print(f"\n📊 Statistiques du jour:")
        print(f"   Pas estimés: {daily_stats['steps_estimated']:,}")
        print(f"   Calories brûlées: {daily_stats['calories_burned']}")
        print(f"   Minutes actives: {daily_stats['active_minutes']}")

        # 3. Alertes actives
        alerts = dashboard['alerts']
        if alerts:
            print(f"\n🚨 Alertes actives ({len(alerts)}):")
            for alert in alerts:
                print(f"   {alert['icon']} {alert['title']} ({alert['severity']})")
        else:
            print(f"\n✅ Aucune alerte active")

        # 4. Recommandations
        print(f"\n💡 Recommandations:")
        for rec in dashboard['recommendations']:
            print(f"   • {rec}")

        return dashboard

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur API: {e}")
        return None

def exemple_widgets_mobiles(dashboard_data: Dict[str, Any]):
    """Exemples de widgets mobiles basés sur les données"""

    print("\n📲 EXEMPLES DE WIDGETS MOBILES")
    print("=" * 50)

    current_activity = dashboard_data['current_activity']

    # Widget Activité Actuelle
    print("🎯 Widget Activité Actuelle:")
    print(f"""
    +---------------------------+
    | {current_activity['emoji']} {current_activity['title']} 
    | {current_activity['subtitle']}
    | {current_activity['value']}
    | Mis à jour: {current_activity['timestamp'][:16]}
    +---------------------------+
    """)

    # Widget Statistiques
    daily_stats = dashboard_data['daily_stats']
    print("📈 Widget Statistiques:")
    print(f"""
    +---------------------------+
    | 👟 {daily_stats['steps_estimated']:,} pas
    | 🔥 {daily_stats['calories_burned']} cal
    | ⏱️ {daily_stats['active_minutes']} min actives
    +---------------------------+
    """)

# === EXEMPLES POUR APPLICATION WEB ===

def exemple_app_web():
    """Exemple d'intégration pour application web (React, Vue, Angular)"""

    print("🌐 EXEMPLE APPLICATION WEB")
    print("=" * 50)

    client = KidjamoAPIClient()
    device_id = "bracelet_001"
    patient_id = "patient_demo_001"

    try:
        # 1. Données actuelles
        current = client.get_current_activity(device_id)

        print("📊 Données Actuelles:")
        print(f"   Device: {current['device_id']}")
        print(f"   Activité: {current['activity']['emoji']} {current['activity']['label']}")
        print(f"   Confiance: {current['activity']['confidence']:.1%}")
        print(f"   Magnitude: {current['accelerometer']['magnitude']:.2f} m/s²")

        # 2. Historique pour graphiques
        history = client.get_activity_history(device_id, hours=24)

        print(f"\n📈 Historique (24h): {len(history)} points de données")
        if history:
            # Calculer quelques statistiques
            magnitudes = [h['magnitude'] for h in history]
            avg_magnitude = sum(magnitudes) / len(magnitudes)
            max_magnitude = max(magnitudes)

            print(f"   Magnitude moyenne: {avg_magnitude:.2f} m/s²")
            print(f"   Magnitude max: {max_magnitude:.2f} m/s²")

            # Répartition des activités
            activity_counts = {}
            for h in history:
                activity = h['activity_level']
                activity_counts[activity] = activity_counts.get(activity, 0) + 1

            print(f"   Répartition activités:")
            for activity, count in activity_counts.items():
                percentage = (count / len(history)) * 100
                print(f"     {activity}: {percentage:.1f}%")

        # 3. Résumé analytique
        summary = client.get_activity_summary(patient_id, "24h")

        print(f"\n📋 Résumé Analytique:")
        print(f"   Période: {summary['time_period']}")
        print(f"   Activité dominante: {summary['dominant_activity']}")
        print(f"   Calories estimées: {summary['calories_estimated']:.0f}")
        print(f"   Pas estimés: {summary['steps_estimated']:,}")

        return {
            'current': current,
            'history': history,
            'summary': summary
        }

    except requests.exceptions.RequestException as e:
        print(f"❌ Erreur API: {e}")
        return None

def generer_code_javascript_react():
    """Génère du code React pour intégrer l'API"""

    print("\n⚛️ CODE REACT EXEMPLE")
    print("=" * 50)

    react_code = '''
// hooks/useKidjamoAPI.js
import { useState, useEffect } from 'react';

export const useCurrentActivity = (deviceId) => {
  const [activity, setActivity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchActivity = async () => {
      try {
        const response = await fetch(`/api/v1/activity/current/${deviceId}`);
        const data = await response.json();
        setActivity(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchActivity();
    const interval = setInterval(fetchActivity, 30000); // Rafraîchir toutes les 30s
    
    return () => clearInterval(interval);
  }, [deviceId]);

  return { activity, loading, error };
};

// components/ActivityCard.jsx
import React from 'react';

export const ActivityCard = ({ deviceId }) => {
  const { activity, loading, error } = useCurrentActivity(deviceId);

  if (loading) return <div>Chargement...</div>;
  if (error) return <div>Erreur: {error}</div>;

  return (
    <div className="activity-card" style={{ color: activity.activity.color }}>
      <div className="activity-emoji">{activity.activity.emoji}</div>
      <h3>{activity.activity.label}</h3>
      <p>{activity.activity.description}</p>
      <div className="magnitude">
        {activity.accelerometer.magnitude.toFixed(2)} m/s²
      </div>
      <div className="confidence">
        Confiance: {(activity.activity.confidence * 100).toFixed(0)}%
      </div>
    </div>
  );
};

// components/ActivityChart.jsx
import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';

export const ActivityChart = ({ deviceId, hours = 24 }) => {
  const [data, setData] = useState([]);

  useEffect(() => {
    fetch(`/api/v1/activity/history/${deviceId}?hours=${hours}`)
      .then(res => res.json())
      .then(setData);
  }, [deviceId, hours]);

  return (
    <LineChart width={600} height={300} data={data}>
      <CartesianGrid strokeDasharray="3 3" />
      <XAxis dataKey="timestamp" />
      <YAxis />
      <Tooltip />
      <Line type="monotone" dataKey="magnitude" stroke="#3b82f6" />
    </LineChart>
  );
};
'''

    print(react_code)

# === EXEMPLE WEBSOCKET TEMPS RÉEL ===

async def exemple_websocket_temps_reel():
    """Exemple d'utilisation des WebSockets pour données temps réel"""

    print("\n🔄 EXEMPLE WEBSOCKET TEMPS RÉEL")
    print("=" * 50)

    device_id = "bracelet_001"
    uri = f"ws://localhost:8000/ws/activity/{device_id}"

    try:
        async with websockets.connect(uri) as websocket:
            print(f"✅ Connecté au WebSocket pour {device_id}")
            print("📡 En attente de données temps réel...")

            # Écouter les messages pendant 30 secondes
            timeout = asyncio.create_task(asyncio.sleep(30))

            while not timeout.done():
                try:
                    # Attendre un message avec timeout
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)

                    print(f"\n📨 Données reçues ({datetime.now().strftime('%H:%M:%S')}):")
                    print(f"   Activité: {data['activity']['emoji']} {data['activity']['label']}")
                    print(f"   Magnitude: {data['accelerometer']['magnitude']:.2f} m/s²")
                    print(f"   Confiance: {data['activity']['confidence']:.1%}")

                except asyncio.TimeoutError:
                    continue
                except websockets.exceptions.ConnectionClosed:
                    print("❌ Connexion WebSocket fermée")
                    break

            print("⏱️ Fin de l'écoute WebSocket")

    except Exception as e:
        print(f"❌ Erreur WebSocket: {e}")
        print("💡 Assurez-vous que l'API est démarrée avec: python main.py")

def generer_code_websocket_javascript():
    """Génère du code JavaScript pour WebSocket"""

    print("\n🌐 CODE WEBSOCKET JAVASCRIPT")
    print("=" * 50)

    js_code = '''
// WebSocket client pour données temps réel
class KidjamoWebSocket {
  constructor(deviceId) {
    this.deviceId = deviceId;
    this.ws = null;
    this.reconnectInterval = 5000;
    this.callbacks = {
      onActivity: [],
      onAlert: [],
      onError: [],
      onConnect: []
    };
  }

  connect() {
    const wsUrl = `ws://localhost:8000/ws/activity/${this.deviceId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('✅ WebSocket connecté');
      this.callbacks.onConnect.forEach(cb => cb());
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('📨 Données reçues:', data);
        this.callbacks.onActivity.forEach(cb => cb(data));
      } catch (error) {
        console.error('❌ Erreur parsing message:', error);
      }
    };

    this.ws.onclose = () => {
      console.log('🔌 WebSocket fermé, reconnexion...');
      setTimeout(() => this.connect(), this.reconnectInterval);
    };

    this.ws.onerror = (error) => {
      console.error('❌ Erreur WebSocket:', error);
      this.callbacks.onError.forEach(cb => cb(error));
    };
  }

  onActivity(callback) {
    this.callbacks.onActivity.push(callback);
  }

  onConnect(callback) {
    this.callbacks.onConnect.push(callback);
  }

  onError(callback) {
    this.callbacks.onError.push(callback);
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Utilisation
const kidjamoWS = new KidjamoWebSocket('bracelet_001');

kidjamoWS.onActivity((data) => {
  // Mettre à jour l'interface
  document.getElementById('activity-emoji').textContent = data.activity.emoji;
  document.getElementById('activity-label').textContent = data.activity.label;
  document.getElementById('magnitude').textContent = data.accelerometer.magnitude.toFixed(2) + ' m/s²';
});

kidjamoWS.connect();
'''

    print(js_code)

# === SCRIPT PRINCIPAL DE DÉMONSTRATION ===

def main():
    """Script principal de démonstration"""

    print("🚀 DÉMONSTRATION API KIDJAMO IoT")
    print("=" * 70)
    print("API pour visualisation des données d'activité et d'accéléromètre")
    print("Optimisée pour applications mobile et web")
    print("=" * 70)

    # Vérifier si l'API est démarrée
    try:
        response = requests.get("http://localhost:8000/", timeout=5)
        if response.status_code == 200:
            print("✅ API démarrée et accessible")
        else:
            print("⚠️ API accessible mais erreur de réponse")
    except requests.exceptions.RequestException:
        print("❌ API non accessible")
        print("💡 Démarrez l'API avec: python main.py")
        print("   Puis relancez ce script")
        return

    # Exemples mobiles
    dashboard_data = exemple_app_mobile()
    if dashboard_data:
        exemple_widgets_mobiles(dashboard_data)

    # Exemples web
    web_data = exemple_app_web()

    # Code React
    generer_code_javascript_react()

    # WebSocket (nécessite une boucle d'événements)
    print("\n🔄 Pour tester les WebSockets, lancez:")
    print("   python -c \"import asyncio; from api_examples import exemple_websocket_temps_reel; asyncio.run(exemple_websocket_temps_reel())\"")

    # Code WebSocket JavaScript
    generer_code_websocket_javascript()

    print("\n🎉 DÉMONSTRATION TERMINÉE")
    print("=" * 50)
    print("📚 Documentation complète disponible sur: http://localhost:8000/docs")
    print("🔧 API Explorer: http://localhost:8000/redoc")

if __name__ == "__main__":
    main()
