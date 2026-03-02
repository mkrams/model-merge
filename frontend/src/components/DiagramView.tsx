import { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import type { PackageData, Element } from '../types';

interface DiagramNode {
  id: string;
  name: string;
  type: string;
  children?: DiagramNode[];
  ports?: { name: string; direction?: string }[];
  width: number;
  height: number;
}

function buildTree(packages: PackageData[]): DiagramNode {
  const root: DiagramNode = {
    id: 'root',
    name: 'Merged Model',
    type: 'root',
    children: [],
    width: 160,
    height: 40,
  };

  for (const pkg of packages) {
    const pkgNode: DiagramNode = {
      id: pkg.id,
      name: pkg.name,
      type: 'package',
      children: [],
      width: Math.max(140, pkg.name.length * 9),
      height: 36,
    };

    // Add part definitions
    for (const pdef of pkg.part_defs) {
      const partNode: DiagramNode = {
        id: pdef.id,
        name: pdef.name,
        type: 'part_def',
        ports: (pdef.ports || []).map((p) => ({ name: p.name, direction: p.direction })),
        children: [],
        width: Math.max(120, pdef.name.length * 8 + 20),
        height: 32 + (pdef.ports?.length || 0) * 16,
      };
      pkgNode.children!.push(partNode);
    }

    // Add port definitions
    for (const pdef of pkg.port_defs) {
      pkgNode.children!.push({
        id: pdef.id,
        name: pdef.name,
        type: 'port_def',
        width: Math.max(100, pdef.name.length * 8),
        height: 28,
      });
    }

    // Add interface definitions
    for (const idef of pkg.interface_defs) {
      pkgNode.children!.push({
        id: idef.id,
        name: idef.name,
        type: 'interface_def',
        width: Math.max(110, idef.name.length * 8),
        height: 28,
      });
    }

    // Add requirement definitions
    for (const rdef of pkg.requirement_defs) {
      pkgNode.children!.push({
        id: rdef.id,
        name: rdef.req_id ? `${rdef.req_id}: ${rdef.name}` : rdef.name,
        type: 'requirement_def',
        width: Math.max(140, (rdef.name?.length || 0) * 7 + 20),
        height: 28,
      });
    }

    // Add parts
    for (const part of pkg.parts) {
      const partChildren: DiagramNode[] = [];
      if (part.children) {
        for (const child of part.children) {
          partChildren.push({
            id: child.id,
            name: child.name,
            type: 'part',
            width: Math.max(100, (child.name?.length || 0) * 8),
            height: 26,
          });
        }
      }
      pkgNode.children!.push({
        id: part.id,
        name: part.name,
        type: 'part',
        children: partChildren.length > 0 ? partChildren : undefined,
        width: Math.max(120, (part.name?.length || 0) * 8 + 20),
        height: 32,
      });
    }

    root.children!.push(pkgNode);
  }

  return root;
}

const nodeColors: Record<string, string> = {
  root: '#1e293b',
  package: '#334155',
  part_def: '#3b82f6',
  part: '#60a5fa',
  port_def: '#8b5cf6',
  interface_def: '#10b981',
  requirement_def: '#f59e0b',
};

export function DiagramView({ packages }: { packages: PackageData[] }) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || packages.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const data = buildTree(packages);
    const root = d3.hierarchy(data);
    const treeLayout = d3.tree<DiagramNode>().nodeSize([180, 80]);
    treeLayout(root);

    const g = svg.append('g');

    // Calculate bounds and center
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    root.each((d) => {
      if (d.x < minX) minX = d.x;
      if (d.x > maxX) maxX = d.x;
      if (d.y < minY) minY = d.y;
      if (d.y > maxY) maxY = d.y;
    });

    const width = maxX - minX + 300;
    const height = maxY - minY + 200;
    svg.attr('viewBox', `${minX - 150} ${minY - 50} ${width} ${height}`);

    // Draw links
    g.selectAll('.link')
      .data(root.links())
      .enter()
      .append('path')
      .attr('class', 'diagram-link')
      .attr('d', (d) => {
        return `M${d.source.x},${d.source.y + 20}
                C${d.source.x},${(d.source.y + d.target.y) / 2}
                 ${d.target.x},${(d.source.y + d.target.y) / 2}
                 ${d.target.x},${d.target.y - 16}`;
      })
      .attr('fill', 'none')
      .attr('stroke', '#475569')
      .attr('stroke-width', 1.5);

    // Draw nodes
    const nodes = g
      .selectAll('.node')
      .data(root.descendants())
      .enter()
      .append('g')
      .attr('transform', (d) => `translate(${d.x},${d.y})`);

    // Node rectangles
    nodes
      .append('rect')
      .attr('x', (d) => -d.data.width / 2)
      .attr('y', -16)
      .attr('width', (d) => d.data.width)
      .attr('height', (d) => d.data.height)
      .attr('rx', 6)
      .attr('fill', (d) => nodeColors[d.data.type] || '#64748b')
      .attr('stroke', '#1e293b')
      .attr('stroke-width', 1)
      .attr('class', 'diagram-node-rect');

    // Node labels
    nodes
      .append('text')
      .attr('y', 4)
      .attr('text-anchor', 'middle')
      .attr('fill', 'white')
      .attr('font-size', '11px')
      .attr('font-weight', '500')
      .text((d) => {
        const name = d.data.name;
        return name.length > 22 ? name.slice(0, 20) + '...' : name;
      });

    // Port indicators
    nodes.each(function (d) {
      if (d.data.ports && d.data.ports.length > 0) {
        const nodeG = d3.select(this);
        d.data.ports.forEach((port, i) => {
          const py = 8 + i * 16;
          nodeG
            .append('circle')
            .attr('cx', d.data.width / 2)
            .attr('cy', py)
            .attr('r', 5)
            .attr('fill', port.direction === 'in' ? '#3b82f6' : '#10b981')
            .attr('stroke', '#fff')
            .attr('stroke-width', 1);
          nodeG
            .append('text')
            .attr('x', d.data.width / 2 + 10)
            .attr('y', py + 4)
            .attr('font-size', '9px')
            .attr('fill', '#94a3b8')
            .text(port.name);
        });
      }
    });

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 3])
      .on('zoom', (event) => {
        g.attr('transform', event.transform);
      });
    svg.call(zoom);

  }, [packages]);

  return (
    <div className="diagram-container">
      <svg ref={svgRef} className="diagram-svg" />
    </div>
  );
}
