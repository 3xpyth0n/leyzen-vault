package compose


const (
	PostgresContainerName = "postgres"
	HAProxyContainerName  = "haproxy"
)


const (
	VaultNetworkName   = "vault-net"
	ControlNetworkName = "control-net"
)


const (
	PostgresDataVolumeName = "postgres-data"
	VaultDataSourceVolume  = "vault-data-source"
)


const (
	VaultWebPort        = 80
	VaultMinReplicas    = 2
	PostgresDefaultPort = 5432
)
