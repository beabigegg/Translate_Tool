import React, { useEffect, useState } from 'react';
import { fetchRouteInfo } from '../../api/config.js';

export function RouteInfoDisplay({ targets }) {
  const [routes, setRoutes] = useState([]);
  const targetsKey = targets?.join(',') || '';

  useEffect(() => {
    if (!targets?.length) { setRoutes([]); return; }
    fetchRouteInfo(targets).then(d => setRoutes(d.routes || []));
  }, [targetsKey]);

  if (!routes.length) return null;
  return (
    <div className="route-info">
      <p className="route-info-title">模型路由</p>
      {routes.map(r => (
        <div key={r.target} className="route-info-row">
          <span>{r.target}</span>
          <span className="route-info-model">{r.model}</span>
        </div>
      ))}
    </div>
  );
}
