// Bivac v2.0.0 (https://camptocamp.github.io/bivac)
// Copyright (c) 2019 Camptocamp
// Licensed under Apache-2.0 (https://raw.githubusercontent.com/camptocamp/bivac/master/LICENSE)
// Modifications copyright (c) 2019 Jam Risser <jam@codejam.ninja>

package restic

import (
	"fmt"

	log "github.com/Sirupsen/logrus"
	"github.com/spf13/cobra"

	"github.com/codejamninja/volback/cmd"
	"github.com/codejamninja/volback/pkg/client"
)

var (
	remoteAddress string
	psk           string
	volumeID      string
)

var envs = make(map[string]string)

var resticCmd = &cobra.Command{
	Use:   "restic --volume [VOLUME_ID] -- [RESTIC_COMMAND]",
	Short: "Run Restic command on a volume's repository",
	Args:  cobra.ArbitraryArgs,
	PreRun: func(cmd *cobra.Command, args []string) {
		if volumeID == "" {
			log.Fatal("You must provide a volume ID.")
			return
		}
	},
	Run: func(cmd *cobra.Command, args []string) {
		c, err := client.NewClient(remoteAddress, psk)
		if err != nil {
			log.Errorf("failed to create new client: %s", err)
			return
		}

		output, err := c.RunRawCommand(volumeID, args)
		if err != nil {
			log.Errorf("failed to run command: %s", err)
			return
		}

		fmt.Println(output)
	},
}

func init() {
	resticCmd.Flags().StringVarP(&remoteAddress, "remote.address", "", "http://127.0.0.1:8182", "Address of the remote Volback server.")
	envs["VOLBACK_REMOTE_ADDRESS"] = "remote.address"

	resticCmd.Flags().StringVarP(&psk, "server.psk", "", "", "Pre-shared key.")
	envs["VOLBACK_SERVER_PSK"] = "server.psk"

	resticCmd.Flags().StringVarP(&volumeID, "volume", "", "", "Volume ID")

	cmd.SetValuesFromEnv(envs, resticCmd.Flags())
	cmd.RootCmd.AddCommand(resticCmd)
}
