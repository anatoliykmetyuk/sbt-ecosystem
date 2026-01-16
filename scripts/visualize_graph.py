#!/usr/bin/env python3
"""
Script to visualize the dependency graph using Bokeh
"""

import sqlite3
import sys
from pathlib import Path
from collections import defaultdict

try:
    from bokeh.plotting import figure, show, save
    from bokeh.models import HoverTool, ColumnDataSource, LabelSet
    from bokeh.io import output_file
    import networkx as nx
except ImportError:
    print("Error: Required packages not installed.")
    print("Please run: pip install bokeh networkx")
    sys.exit(1)

DB_PATH = Path(__file__).parent.parent / "database" / "sbt_ecosystem.db"

def load_graph_data():
    """Load all nodes and edges from the database"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Load repositories
    cursor.execute("""
        SELECT id, url, organization, name, status
        FROM repositories
    """)
    repositories = {row['id']: row for row in cursor.fetchall()}

    # Load artifacts
    cursor.execute("""
        SELECT id, organization, name, is_plugin, repository_id
        FROM artifacts
    """)
    artifacts = {row['id']: row for row in cursor.fetchall()}

    # Load repository plugin dependencies
    cursor.execute("""
        SELECT repository_id, plugin_artifact_id, version
        FROM repository_plugin_dependencies
    """)
    repo_plugin_edges = cursor.fetchall()

    # Load artifact dependencies
    cursor.execute("""
        SELECT dependent_artifact_id, dependency_artifact_id, version, scope
        FROM artifact_dependencies
    """)
    artifact_edges = cursor.fetchall()

    conn.close()

    return repositories, artifacts, repo_plugin_edges, artifact_edges

def build_graph(repositories, artifacts, repo_plugin_edges, artifact_edges):
    """Build NetworkX graph and prepare data for Bokeh"""
    G = nx.Graph()

    # Add repository nodes
    repo_nodes = {}
    for repo_id, repo in repositories.items():
        node_id = f"repo_{repo_id}"
        label = f"{repo['organization']}/{repo['name']}"
        G.add_node(node_id,
                   type='repository',
                   label=label,
                   full_label=f"{repo['organization']}/{repo['name']}",
                   status=repo['status'],
                   repo_id=repo_id)
        repo_nodes[repo_id] = node_id

    # Add artifact nodes
    artifact_nodes = {}
    for art_id, art in artifacts.items():
        node_id = f"art_{art_id}"
        label = f"{art['organization']}:{art['name']}"
        G.add_node(node_id,
                   type='artifact',
                   label=label,
                   full_label=label,
                   is_plugin=bool(art['is_plugin']),
                   repository_id=art['repository_id'],
                   art_id=art_id)
        artifact_nodes[art_id] = node_id

    # Add repository -> plugin edges
    for repo_id, plugin_id, version in repo_plugin_edges:
        repo_node = repo_nodes.get(repo_id)
        plugin_node = artifact_nodes.get(plugin_id)
        if repo_node and plugin_node:
            G.add_edge(repo_node, plugin_node,
                      type='repo_plugin',
                      version=version)

    # Add artifact -> artifact edges
    for dep_id, dep_on_id, version, scope in artifact_edges:
        dep_node = artifact_nodes.get(dep_id)
        dep_on_node = artifact_nodes.get(dep_on_id)
        if dep_node and dep_on_node:
            G.add_edge(dep_node, dep_on_node,
                      type='artifact_dep',
                      version=version,
                      scope=scope)

    return G, repo_nodes, artifact_nodes

def create_visualization(G, repo_nodes, artifact_nodes):
    """Create Bokeh visualization"""
    # Use spring layout for positioning
    pos = nx.spring_layout(G, k=2, iterations=50)

    # Separate nodes by type
    repo_node_ids = list(repo_nodes.values())
    artifact_node_ids = [n for n in G.nodes() if n not in repo_node_ids]

    # Prepare data sources
    repo_x = [pos[node][0] for node in repo_node_ids]
    repo_y = [pos[node][1] for node in repo_node_ids]
    repo_labels = [G.nodes[node]['full_label'] for node in repo_node_ids]
    repo_statuses = [G.nodes[node]['status'] for node in repo_node_ids]

    art_x = [pos[node][0] for node in artifact_node_ids]
    art_y = [pos[node][1] for node in artifact_node_ids]
    art_labels = [G.nodes[node]['full_label'] for node in artifact_node_ids]
    art_is_plugin = [G.nodes[node].get('is_plugin', False) for node in artifact_node_ids]

    # Prepare edge data
    edge_xs = []
    edge_ys = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_xs.append([x0, x1])
        edge_ys.append([y0, y1])

    # Create figure
    p = figure(
        title="SBT Ecosystem Dependency Graph",
        x_range=(-2, 2),
        y_range=(-2, 2),
        width=1200,
        height=800,
        tools="pan,wheel_zoom,box_zoom,reset,save",
        toolbar_location="above"
    )

    # Draw edges
    p.multi_line(edge_xs, edge_ys, line_color="gray", line_alpha=0.6, line_width=1)

    # Draw repository nodes (blue)
    repo_source = ColumnDataSource(data=dict(
        x=repo_x,
        y=repo_y,
        label=repo_labels,
        status=repo_statuses,
        type=['Repository'] * len(repo_labels)
    ))
    repo_circles = p.scatter('x', 'y', size=15, color='#2E86AB', alpha=0.8, source=repo_source,
             legend_label="Repositories")

    # Draw artifact nodes (green for libraries, orange for plugins)
    plugin_x = [art_x[i] for i, is_plugin in enumerate(art_is_plugin) if is_plugin]
    plugin_y = [art_y[i] for i, is_plugin in enumerate(art_is_plugin) if is_plugin]
    plugin_labels = [art_labels[i] for i, is_plugin in enumerate(art_is_plugin) if is_plugin]

    library_x = [art_x[i] for i, is_plugin in enumerate(art_is_plugin) if not is_plugin]
    library_y = [art_y[i] for i, is_plugin in enumerate(art_is_plugin) if not is_plugin]
    library_labels = [art_labels[i] for i, is_plugin in enumerate(art_is_plugin) if not is_plugin]

    plugin_circles = None
    library_circles = None

    if plugin_x:
        plugin_source = ColumnDataSource(data=dict(
            x=plugin_x,
            y=plugin_y,
            label=plugin_labels,
            type=['Plugin'] * len(plugin_labels)
        ))
        plugin_circles = p.scatter('x', 'y', size=12, color='#F18F01', alpha=0.8, source=plugin_source,
                 legend_label="Plugins")

    if library_x:
        library_source = ColumnDataSource(data=dict(
            x=library_x,
            y=library_y,
            label=library_labels,
            type=['Library'] * len(library_labels)
        ))
        library_circles = p.scatter('x', 'y', size=12, color='#06A77D', alpha=0.8, source=library_source,
                 legend_label="Libraries")

    # Add labels for all nodes
    all_x = repo_x + art_x
    all_y = repo_y + art_y
    all_labels = repo_labels + art_labels

    label_source = ColumnDataSource(data=dict(
        x=all_x,
        y=all_y,
        label=all_labels
    ))

    labels = LabelSet(x='x', y='y', text='label', level='overlay',
                     text_font_size='8pt', text_color='black',
                     x_offset=5, y_offset=5, source=label_source)
    p.add_layout(labels)

    # Add hover tool for all node types
    hover_tooltips = [
        ("Label", "@label"),
        ("Type", "@type"),
    ]

    hover = HoverTool(tooltips=hover_tooltips, renderers=[repo_circles])
    if plugin_circles:
        hover_plugin = HoverTool(tooltips=hover_tooltips, renderers=[plugin_circles])
        p.add_tools(hover_plugin)
    if library_circles:
        hover_lib = HoverTool(tooltips=hover_tooltips, renderers=[library_circles])
        p.add_tools(hover_lib)
    p.add_tools(hover)

    # Style
    p.legend.location = "top_left"
    p.legend.click_policy = "hide"
    p.background_fill_color = "white"
    p.grid.grid_line_color = "lightgray"

    return p

def main():
    print("Loading graph data from database...")
    repositories, artifacts, repo_plugin_edges, artifact_edges = load_graph_data()

    print(f"Found {len(repositories)} repositories, {len(artifacts)} artifacts")
    print(f"Found {len(repo_plugin_edges)} repo-plugin dependencies, {len(artifact_edges)} artifact dependencies")

    print("Building graph...")
    G, repo_nodes, artifact_nodes = build_graph(repositories, artifacts, repo_plugin_edges, artifact_edges)

    print(f"Graph has {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")

    print("Creating visualization...")
    p = create_visualization(G, repo_nodes, artifact_nodes)

    output_file(Path(__file__).parent.parent / "database" / "dependency_graph.html")
    print("Saving visualization to database/dependency_graph.html")
    save(p)
    print("✓ Visualization saved! Open dependency_graph.html in your browser.")

if __name__ == "__main__":
    main()
