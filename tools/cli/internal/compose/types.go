package compose


type ServiceDefinition struct {
	Image           string                        `yaml:"image,omitempty"`
	Build           *BuildDefinition              `yaml:"build,omitempty"`
	ContainerName   string                        `yaml:"container_name,omitempty"`
	Restart         string                        `yaml:"restart,omitempty"`
	Environment     map[string]string             `yaml:"environment,omitempty"`
	EnvFile         []string                      `yaml:"env_file,omitempty"`
	Expose          []string                      `yaml:"expose,omitempty"`
	Ports           []string                      `yaml:"ports,omitempty"`
	Volumes         []string                      `yaml:"volumes,omitempty"`
	Networks        []string                      `yaml:"networks,omitempty"`
	DependsOn       map[string]DependsOnCondition `yaml:"depends_on,omitempty"`
	HealthCheck     *HealthCheckDefinition        `yaml:"healthcheck,omitempty"`
	Tmpfs           []string                      `yaml:"tmpfs,omitempty"`
	StopGracePeriod string                        `yaml:"stop_grace_period,omitempty"`
	Command         interface{}                   `yaml:"command,omitempty"`
	User            string                        `yaml:"user,omitempty"`
}


type BuildDefinition struct {
	Context    string `yaml:"context,omitempty"`
	Dockerfile string `yaml:"dockerfile,omitempty"`
}


type DependsOnCondition struct {
	Condition string `yaml:"condition,omitempty"`
}


type HealthCheckDefinition struct {
	Test        []string `yaml:"test,omitempty"`
	Interval    string   `yaml:"interval,omitempty"`
	Timeout     string   `yaml:"timeout,omitempty"`
	Retries     int      `yaml:"retries,omitempty"`
	StartPeriod string   `yaml:"start_period,omitempty"`
}


type VolumeDefinition struct {
	Name   string `yaml:"name,omitempty"`
	Driver string `yaml:"driver,omitempty"`
}


type NetworkDefinition struct {
	Name   string `yaml:"name,omitempty"`
	Driver string `yaml:"driver,omitempty"`
}


type Manifest struct {
	Services map[string]ServiceDefinition `yaml:"services"`
	Volumes  map[string]VolumeDefinition  `yaml:"volumes,omitempty"`
	Networks map[string]NetworkDefinition `yaml:"networks,omitempty"`
}
