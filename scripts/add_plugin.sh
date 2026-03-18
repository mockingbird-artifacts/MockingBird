#!/bin/bash

plugin_config=$(cat <<'EOF'
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-jar-plugin</artifactId>
    <version>3.2.0</version>
    <configuration>
        <excludes>
            <exclude>module-info.class</exclude>
        </excludes>
    </configuration>
    <executions>
        <execution>
            <goals>
                <goal>test-jar</goal>
            </goals>
        </execution>
    </executions>
</plugin>
EOF
)

if [ $# -ne 2 ]; then
    echo "Usage: ./add_plugin.sh <project_name> <project_dir>"
    exit 1
fi

project_name="$1"
project_dir="$2"
original_dir="$project_dir/$project_name"

if [ ! -d "$original_dir" ]; then
    echo "Error: Project '$project_name' not found in $project_dir."
    exit 1
fi

cd "$original_dir" || exit

if [ ! -f "pom.xml" ]; then
    echo "Error: pom.xml not found in $original_dir."
    exit 1
fi

awk '
    BEGIN { in_build = 0 }
    /<build>/ { in_build = 1 }
    /<\/build>/ { in_build = 0 }
    in_build && /<plugins>/ {
        print;
        while ((getline line < "/dev/stdin") > 0) print line;
        next;
    }
    { print }
' pom.xml <<< "$plugin_config" > pom.xml.new && mv pom.xml.new pom.xml

echo "Plugin configuration added to pom.xml in $original_dir."
