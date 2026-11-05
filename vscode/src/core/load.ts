import { HubClient } from './client';
import { buildModel, Model } from './model';

/** Fetch alarms, findings, graph and triage for one project and fold them into a Model. */
export async function loadModel(c: HubClient, pid: string): Promise<Model> {
  const [alarms, findings, graph, triage] = await Promise.all([c.alarms(pid), c.findings(pid), c.graph(pid), c.triage(pid)]);
  return buildModel(alarms, findings, graph, triage);
}
